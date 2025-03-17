import os
import sys
import time
import json
import threading
from datetime import datetime
import statistics

import libtorrent as lt
import uvicorn
from fastapi import FastAPI
from rich import inspect

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from utils import Statistics, ExperimentConfig, ResultsManager, ProgressDisplay

FINISHED_CLIENTS = []
LOGGED = False
MX_TIME = 0.0

app = FastAPI()
router = FastAPI().router

@router.post("/ack")
def ack(data: dict):
    global FINISHED_CLIENTS
    global MX_TIME
    print(f"Client {data['client']} finished.")
    FINISHED_CLIENTS.append(data['client'])
    MX_TIME = max(MX_TIME, data['time'])
    return {"acknowledged": True}

@router.get("/ready")
def ready(client: str):
    global LOGGED
    global FINISHED_CLIENTS
    global MX_TIME
    if len(FINISHED_CLIENTS) == 3 and LOGGED:
        FINISHED_CLIENTS = []
        LOGGED = False
        MX_TIME = 0.0
    return {"ready": client not in FINISHED_CLIENTS}

app.include_router(router)

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False, workers=1)

def main():
    global FINISHED_CLIENTS
    global LOGGED
    
    api_thread = threading.Thread(target=run_api)
    api_thread.start()
    
    if os.path.exists("seeder_metrics.json"):
        os.remove("seeder_metrics.json")
        
    if len(sys.argv) != 2:
        print("Usage: python seeder.py <file_path>")
        sys.exit(1)

    file_path = os.path.abspath(sys.argv[1])
    if not os.path.isfile(file_path):
        print("Error: Provided file does not exist.")
        sys.exit(1)
    
    file_size = os.path.getsize(file_path)
    ses = lt.session({'listen_interfaces': '0.0.0.0:6882'})

    fs = lt.file_storage()
    lt.add_files(fs, file_path)

    torrent_creator = lt.create_torrent(fs)
    tracker_url = "udp://tracker.openbittorrent.com:80"
    torrent_creator.add_tracker(tracker_url)

    print(f"Calculating piece hashes for {os.path.basename(file_path)}... (this may take a while)")
    lt.set_piece_hashes(torrent_creator, os.path.dirname(file_path))

    torrent_data = torrent_creator.generate()
    ti = lt.torrent_info(torrent_data)

    info_hash = str(ti.info_hash())
    filename = os.path.basename(file_path)
    magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={filename}&tr={tracker_url}"
    print("Magnet link:")
    print(magnet_link)

    metrics_log = []
    transfer_start_time = None
    active_peers = {}
    
    def add_new_torrent():
        nonlocal start_time, transfer_start_time, active_peers
        active_peers = {}
        start_time = time.time()
        transfer_start_time = None
        return ses.add_torrent({
            'ti': ti,
            'save_path': os.path.dirname(file_path),
            'flags': lt.torrent_flags.seed_mode
        })

    h = add_new_torrent()
    log_file = str(time.strftime("%Y%m%d-%H%M%S"))+"_seeder_metrics.json"

    print(f"Seeding {filename}. Press Ctrl+C to stop.")
    start_time = time.time()

    try:
        while True:
            s = h.status()
            print("finished clients", FINISHED_CLIENTS)

            print(f"\rSeeding {ti.name()}: up: {s.upload_rate / 1000:.1f} kB/s, "
                  f"peers: {s.num_peers}, "
                  f"total uploaded: {s.total_payload_upload / 1024:.1f} kB", end='')
            sys.stdout.flush()

            peers = h.get_peer_info()
            inspect(peers)
            print("peers", peers)
            print("peers len", len(peers))
            current_time = time.time()
            if len(peers) > 0:
                print("Entered peers")
                sys.stdout.flush()
                
                if transfer_start_time is None:
                    transfer_start_time = current_time

                for peer in peers:
                    peer_ip, peer_port = peer.ip  
                    peer_id = f"{peer_ip}:{peer_port}"

                    if peer_id not in active_peers:
                        active_peers[peer_id] = {
                            "start": current_time,
                            "completed": False,
                            "finish": None,
                        }

                    if not active_peers[peer_id]["completed"] and peer.progress >= 0.99:
                        active_peers[peer_id]["completed"] = True
                        active_peers[peer_id]["finish"] = current_time
                        elapsed = current_time - active_peers[peer_id]["start"]
                        print(f"\nPeer {peer_id} completed transfer in {elapsed:.2f} seconds.")
                        sys.stdout.flush()

            else:
                print("\nNo peers connected yet.")

            if len(FINISHED_CLIENTS) == 3 and not LOGGED:
                end_time = MX_TIME
                effective_start = transfer_start_time if transfer_start_time is not None else start_time
                total_seeding_time = end_time - effective_start

                peer_details = {}
                for pid, details in active_peers.items():
                    transfer_time = (details["finish"] - details["start"]) if details["completed"] else None
                    peer_details[pid] = {
                        "start_time": details["start"],
                        "finish_time": details["finish"],
                        "transfer_time": transfer_time,
                        "completed": details["completed"]
                    }

                summary_log = {
                    "transfer_time": total_seeding_time,
                    "throughput": (s.total_payload_upload * 0.008 / total_seeding_time if total_seeding_time > 0 else 0),
                    "file_size": file_size,
                    "info_hash": info_hash,
                    "total_app_data": s.total_payload_upload,
                    "overhead_ratio": s.total_upload / s.total_payload_upload,
                    "header_size": s.total_upload - s.total_payload_upload,
                    "run_payload_uploaded": s.total_payload_upload,
                    "total_seeding_time_seconds": total_seeding_time,
                    "total_payload_uploaded": s.total_payload_upload,
                    "total_data_uploaded": s.total_upload,
                    "protocol_overhead_bytes": s.total_upload - s.total_payload_upload,
                    "total_peers_connected": len(active_peers),
                    "peer_details": peer_details,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                existing_logs = []
                if os.path.exists(log_file):
                    try:
                        with open(log_file, 'r') as f:
                            existing_logs = json.load(f)
                    except json.JSONDecodeError:
                        print(f"Warning: Could not parse existing {log_file}, creating new log")
                combined_logs = existing_logs + [summary_log]
                with open(log_file, 'w') as f:
                    json.dump(combined_logs, f, indent=2)

                print(f"\nThreshold reached. Logged transfer details to {log_file}. Restarting seeding...")

                ses.remove_torrent(h)
                h = add_new_torrent()
                LOGGED = True

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down seeder.")

        try:
            with open(log_file, 'r') as f:
                all_logs = json.load(f)
        except Exception as e:
            print("Error reading seeder_metrics.json:", e)
            sys.exit(1)

        throughput_list = [run["throughput"] for run in all_logs if run.get("throughput", 0) > 0]
        if throughput_list:
            mean_throughput = statistics.mean(throughput_list)
            stdev_throughput = statistics.stdev(throughput_list) if len(throughput_list) > 1 else 0
        else:
            mean_throughput = stdev_throughput = 0

        ratio_list = [run["overhead_ratio"] for run in all_logs]
        if ratio_list:
            avg_ratio = statistics.mean(ratio_list)
        else:
            avg_ratio = 0

        final_summary = {
            "mean_throughput": mean_throughput,
            "std_throughput": stdev_throughput,
            "avg_data_to_size_ratio": avg_ratio,
            "file_size": file_size,
            "num_runs": len(all_logs)
        }
        final_summary_file = str(file_size)+str(time.strftime("%Y%m%d-%H%M%S"))+"_final_summary.json"
        with open(final_summary_file, 'w') as f:
            json.dump(final_summary, f, indent=2)
        print(f"Final summary written to {final_summary_file}")

        summ = Statistics.process_experiment_results(all_logs, str(file_size))
        print(summ)
        results_data = ResultsManager.initialize_results(
            "p2p BitTorrent", "vm1", "A"
        )
        if summ:
            results_data["files"][str(file_size)] = summ
            ResultsManager.save_results(results_data, "bitTorrent", str(file_size), "vm1", current_dir)
        print("Seeder shutdown complete")
        sys.exit(0)

if __name__ == "__main__":
    main()