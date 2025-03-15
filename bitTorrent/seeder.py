import libtorrent as lt
import time
import sys
import os
import json
from datetime import datetime
from rich import inspect

def main():
    # Check for correct number of arguments
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
    tracker_url = "udp://tracker.opentrackr.org:1337"
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
    
    # Add torrent to session in seed mode
    h = ses.add_torrent({
        'ti': ti,
        'save_path': os.path.dirname(file_path),
        'flags': lt.torrent_flags.seed_mode
    })
    
    # Dictionary to track active transfers
    active_peers = {}
    
    # Track global metrics
    start_time = time.time()
    
    # Start seeding
    print(f"Seeding {filename}. Press Ctrl+C to stop.")
    
    try:
        while True:
            s = h.status()
            inspect(s)
            # Display status
            print(f"\rSeeding {ti.name()}: "
                  f"up: {s.upload_rate / 1000:.1f} kB/s, "
                  f"peers: {s.num_peers}, "
                  f"total uploaded: {s.total_payload_upload/1024:.1f} kB", end='')
            sys.stdout.flush()
            time.sleep(1)
            
    except KeyboardInterrupt:
        # Calculate total seeding metrics
        end_time = time.time()
        total_seeding_time = end_time - start_time
        
        # Add summary entry
        summary_log = {
            "file": filename,
            "info_hash": info_hash,
            "total_seeding_time_seconds": total_seeding_time,
            "total_payload_uploaded": h.status().total_payload_upload,
            "total_data_uploaded": h.status().total_upload,
            "protocol_overhead_bytes": h.status().total_upload - h.status().total_payload_upload,
            "average_upload_rate": h.status().total_payload_upload / total_seeding_time if total_seeding_time > 0 else 0,
            "total_peers_connected": len(active_peers),
            "completed_transfers": sum(1 for p in active_peers.values() if p["completed"]),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Add summary to log
        metrics_log.append(summary_log)
        
        # Now write the entire log to file at once
        log_file = "seeder_metrics.json"
        
        # Check if file already exists and has content
        existing_logs = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    existing_logs = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse existing {log_file}, creating new log")
        
        # Combine existing logs with new logs
        combined_logs = existing_logs + metrics_log
        
        # Write all logs to file
        with open(log_file, 'w') as f:
            json.dump(combined_logs, f, indent=2)
        
        print(f"\nShutting down seeder. Logged {len(metrics_log)-1} transfers to {log_file}")
        sys.exit(0)

if __name__ == "__main__":
    main()