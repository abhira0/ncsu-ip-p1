import libtorrent as lt
import uvicorn
import time
import sys
import os
import json
import statistics
from datetime import datetime
from rich import inspect
import threading
from fastapi import FastAPI
from fastapi import APIRouter
import fastapi
router = fastapi.APIRouter()


FINISHED_CLIENTS = []
LOGGED = False

@router.post("/ack")
def ack(data: dict):
    global FINISHED_CLIENTS
    print(f"Client {data['client']} finished.")
    FINISHED_CLIENTS.append(data['client'])
    return {"acknowledged": True}

@router.get("/ready")
def ready(client: str):
    global LOGGED
    global FINISHED_CLIENTS
    if len(FINISHED_CLIENTS) == 3 and LOGGED:
        FINISHED_CLIENTS = []
        LOGGED = False
        
    return {"ready": client not in FINISHED_CLIENTS}

app = FastAPI()
app.include_router(router)

def run_api():

    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False, workers=1)
def main():
    global FINISHED_CLIENTS
    global LOGGED
    global is_ready
        # Start the API server in a background thread
    api_thread = threading.Thread(target=run_api)
    api_thread.start()
    # Remove any existing metrics file
    if os.path.exists("seeder_metrics.json"):
        os.remove("seeder_metrics.json")
        
    if len(sys.argv) != 2:
        print("Usage: python seeder.py <file_path>")
        sys.exit(1)

    # Get the absolute file path and validate it
    file_path = os.path.abspath(sys.argv[1])
    if not os.path.isfile(file_path):
        print("Error: Provided file does not exist.")
        sys.exit(1)
    
    # Get file size for later ratio calculations
    file_size = os.path.getsize(file_path)

    # Initialize libtorrent session
    ses = lt.session({'listen_interfaces': '0.0.0.0:6882'})

    # Create file storage and add the single file
    fs = lt.file_storage()
    lt.add_files(fs, file_path)

    # Create the torrent
    torrent_creator = lt.create_torrent(fs)

    # Add the private tracker (running on your Mac) 
    tracker_url = "udp://tracker.openbittorrent.com:80"
    torrent_creator.add_tracker(tracker_url)

    # Compute piece hashes
    print(f"Calculating piece hashes for {os.path.basename(file_path)}... (this may take a while)")
    lt.set_piece_hashes(torrent_creator, os.path.dirname(file_path))

    # Generate torrent data and torrent_info object
    torrent_data = torrent_creator.generate()
    ti = lt.torrent_info(torrent_data)

    # Generate and print the magnet link
    info_hash = str(ti.info_hash())
    filename = os.path.basename(file_path)
    magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={filename}&tr={tracker_url}"
    print("Magnet link:")
    print(magnet_link)

    # Initialize an in-memory log
    metrics_log = []

    # Global variables for run timing
    transfer_start_time = None # will be set when the first peer requests the file

    # Dictionary to track active transfers
    active_peers = {}

    # Function to add the torrent and reset run metrics
    def add_new_torrent():
        nonlocal start_time, transfer_start_time, active_peers
        active_peers = {}
        start_time = time.time()
        transfer_start_time = None  # Reset so that the next transfer's timestamp is captured
        return ses.add_torrent({
            'ti': ti,
            'save_path': os.path.dirname(file_path),
            'flags': lt.torrent_flags.seed_mode
        })

    # Start the first run
    h = add_new_torrent()
    log_file = str(time.strftime("%Y%m%d-%H%M%S"))+"_seeder_metrics.json"

    print(f"Seeding {filename}. Press Ctrl+C to stop.")
    start_time = time.time()   # time when torrent is added

    try:
        while True:
            s = h.status()
            print("finished clients",FINISHED_CLIENTS)  # Debug: displays the status object

            # Display aggregated status
            print(f"\rSeeding {ti.name()}: up: {s.upload_rate / 1000:.1f} kB/s, "
                  f"peers: {s.num_peers}, "
                  f"total uploaded: {s.total_payload_upload / 1024:.1f} kB", end='')
            sys.stdout.flush()

            # Poll peer details
            peers = h.get_peer_info()
            inspect(peers)  # Debug: displays the peer info
            print("peers",peers)
            print("peers len",len(peers))
            current_time = time.time()
            if len(peers) > 0:
                print("Entered peers")
                sys.stdout.flush()
                # Set transfer_start_time when the first peer is seen
                if transfer_start_time is None:
                    transfer_start_time = current_time

                for peer in peers:
                    # Unpack the IP tuple to get both IP and port
                    peer_ip, peer_port = peer.ip  
                    peer_id = f"{peer_ip}:{peer_port}"

                    # Record the peer's first appearance if not already tracked
                    if peer_id not in active_peers:
                        active_peers[peer_id] = {
                            "start": current_time,
                            "completed": False,
                            "finish": None,
                        }

                    # Check if the peer has completed (progress is nearly 100%)
                    if not active_peers[peer_id]["completed"] and peer.progress >= 0.99:
                        active_peers[peer_id]["completed"] = True
                        active_peers[peer_id]["finish"] = current_time
                        elapsed = current_time - active_peers[peer_id]["start"]
                        print(f"\nPeer {peer_id} completed transfer in {elapsed:.2f} seconds.")
                        sys.stdout.flush()

            else:
                print("\nNo peers connected yet.")

            # Check if payload threshold is reached for this run
            if len(FINISHED_CLIENTS) == 3 and not LOGGED:
                end_time = time.time()
                # Use transfer_start_time if available; otherwise, fallback to start_time
                effective_start = transfer_start_time if transfer_start_time is not None else start_time
                total_seeding_time = end_time - effective_start

                # Prepare a summary log including each peer’s transfer time
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
                    "file": filename,
                    "info_hash": info_hash,
                    "run_payload_uploaded": s.total_payload_upload,
                    "total_seeding_time_seconds": total_seeding_time,
                    "total_payload_uploaded": s.total_payload_upload,
                    "total_data_uploaded": s.total_upload,
                    "protocol_overhead_bytes": s.total_upload - s.total_payload_upload,
                    # Throughput computed here with a conversion factor (adjust as needed)
                    "throughput": (s.total_payload_upload * 0.008 / total_seeding_time if total_seeding_time > 0 else 0),
                    "total_peers_connected": len(active_peers),
                    "peer_details": peer_details,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                # Append the run summary to the JSON log file
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

                # Remove the current torrent from the session and re-add it for a new run
                ses.remove_torrent(h)
                h = add_new_torrent()
                LOGGED = True

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down seeder.")

        # Process the JSON log file to compute final statistics.
        try:
            with open(log_file, 'r') as f:
                all_logs = json.load(f)
        except Exception as e:
            print("Error reading seeder_metrics.json:", e)
            sys.exit(1)

        # Extract throughput values and compute mean and standard deviation.
        throughput_list = [run["throughput"] for run in all_logs if run.get("throughput", 0) > 0]
        if throughput_list:
            mean_throughput = statistics.mean(throughput_list)
            stdev_throughput = statistics.stdev(throughput_list) if len(throughput_list) > 1 else 0
        else:
            mean_throughput = stdev_throughput = 0

        # Compute the ratio (total_payload_uploaded / file_size) for each run and then average.
        ratio_list = [run["total_data_uploaded"] / (3*file_size) for run in all_logs if run.get("total_data_uploaded", 0) > 0]
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

        sys.exit(0)

if __name__ == "__main__":
    main()