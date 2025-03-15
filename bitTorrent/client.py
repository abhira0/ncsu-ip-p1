import libtorrent as lt
import time
import sys
import os
import shutil

def run_download(magnet_link, run_number):
    print(f"\n=== Starting download run {run_number} ===")
    # Ensure download directory exists
    download_path = "./downloads"
    os.makedirs(download_path, exist_ok=True)

    # Initialize libtorrent session
    ses = lt.session({'listen_interfaces': '0.0.0.0:6881'})

    # Add torrent using the magnet link
    params = lt.parse_magnet_uri(magnet_link)
    params.save_path = download_path
    handle = ses.add_torrent(params)

    # Wait for metadata
    while not handle.status().has_metadata:
        time.sleep(1)

    s = handle.status()
    print(f"Downloading {s.name} ({s.total_wanted} bytes)")

    # Record start time for throughput calculation
    start_time = time.time()

    # Monitor download progress until complete
    while handle.status().progress < 1.0:
        s = handle.status()
        print(f"\rProgress: {s.progress * 100:.2f}% "
              f"(down: {s.download_rate / 1000:.1f} kB/s, "
              f"peers: {s.num_peers})", end=' ')
        sys.stdout.flush()
        time.sleep(1)

    end_time = time.time()
    print("\nDownload complete.")

    # Calculate client-side metrics
    s = handle.status()
    total_time = end_time - start_time
    payload_transferred = s.total_payload_download  # Actual file data downloaded
    total_data_transferred = s.total_download         # Total data including overhead
    overhead = total_data_transferred - payload_transferred
    throughput = payload_transferred / total_time if total_time > 0 else 0

    print("\nClient Metrics:")
    print(f"  Payload Transferred: {payload_transferred} bytes")
    print(f"  Total Data Transferred: {total_data_transferred} bytes")
    print(f"  Overhead: {overhead} bytes")
    print(f"  Throughput: {throughput:.2f} bytes/second")

    # Cleanly pause and remove the session
    ses.pause()
    del ses

def main():
    # Expect two arguments: magnet_link and runs (number of download cycles)
    if len(sys.argv) != 3:
        print("Usage: python client.py <magnet_link> <runs>")
        sys.exit(1)

    magnet_link = sys.argv[1]
    try:
        runs = int(sys.argv[2])
    except ValueError:
        print("Error: runs must be an integer.")
        sys.exit(1)

    for run in range(1, runs + 1):
        run_download(magnet_link, run)
        # Clean up downloads folder after each run
        print("Deleting downloads folder...")
        shutil.rmtree("./downloads", ignore_errors=True)
        # Optionally, wait a few seconds for the seeder to restart before next run
        time.sleep(2)

if __name__ == "__main__":
    try:
        main()
    finally:
        # Ensure downloads folder is removed on exit.
        print("\nFinal cleanup: Deleting downloads folder...")
        shutil.rmtree("./downloads", ignore_errors=True)