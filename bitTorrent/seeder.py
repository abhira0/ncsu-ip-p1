import libtorrent as lt
import time
import sys
import os
import json
from datetime import datetime
from rich import inspect

def main():
    # Check for correct number of arguments
    if os.path.exists("seeder_metrics.json"): os.remove("seeder_metrics.json")
    if len(sys.argv) != 2:
        print("Usage: python seeder.py <file_path>")
        sys.exit(1)

    # Get the absolute file path and validate it
    file_path = os.path.abspath(sys.argv[1])
    if not os.path.isfile(file_path):
        print("Error: Provided file does not exist.")
        sys.exit(1)

    # Initialize libtorrent session
    ses = lt.session({'listen_interfaces': '0.0.0.0:6882'})

    # Create file storage and add the single file
    fs = lt.file_storage()
    lt.add_files(fs, file_path)

    # Create the torrent
    torrent_creator = lt.create_torrent(fs)

    # Add the open tracker
    tracker_url = "http://192.168.68.106:8000/announce"
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
    # start_time remains as when we add the torrent to the session
    start_time = time.time()
    # transfer_start_time will be set when the first peer requests the file
    transfer_start_time = None

    # Dictionary to track active transfers
    active_peers = {}

    # Function to add the torrent and reset run metrics
    def add_new_torrent():
        nonlocal start_time, transfer_start_time, active_peers
        # Reset per-run metrics and set new start time for torrent addition
        active_peers = {}
        start_time = time.time()
        transfer_start_time = None  # Reset this so we capture the next request's timestamp
        return ses.add_torrent({
            'ti': ti,
            'save_path': os.path.dirname(file_path),
            'flags': lt.torrent_flags.seed_mode
        })

    # Start first run
    h = add_new_torrent()

    print(f"Seeding {filename}. Press Ctrl+C to stop.")

    try:
        while True:
            s = h.status()
            inspect(s)  # For debugging, displays the status object

            # Display aggregated status
            print(f"\rSeeding {ti.name()}: up: {s.upload_rate / 1000:.1f} kB/s, "
                  f"peers: {s.num_peers}, "
                  f"total uploaded: {s.total_payload_upload/1024:.1f} kB", end='')
            sys.stdout.flush()

            # Poll peer details
            peers = h.get_peer_info()
            current_time = time.time()
            if peers:
                # If we haven't set transfer_start_time yet, do it now
                if transfer_start_time is None:
                    transfer_start_time = current_time

                for peer in peers:
                    # Unpack the ip tuple to get both IP and port
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
            else:
                print("\nNo peers connected yet.")

            # Check if payload threshold is reached for this run
            if s.total_payload_upload >= 30720:
                end_time = time.time()
                # Use transfer_start_time if available, otherwise fall back to start_time
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
                    "throughput": (s.total_payload_upload *0.008 / total_seeding_time if total_seeding_time > 0 else 0),
                    "total_peers_connected": len(active_peers),
                    "peer_details": peer_details,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                # Write the summary to a log file
                log_file = "seeder_metrics.json"
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

                # Remove the current torrent from the session
                ses.remove_torrent(h)

                # Re-add the torrent to begin a new run (timer and metrics reset)
                h = add_new_torrent()

            time.sleep(1)

    except KeyboardInterrupt:
        # Log final metrics on manual interrupt
        print(f"\nShutting down seeder. Logged final transfer details to {log_file}")
        sys.exit(0)

if __name__ == "__main__":
    main()