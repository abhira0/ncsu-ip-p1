import libtorrent as lt
import time
import sys
import os
import shutil

def main():
    # Check for correct number of arguments
    if len(sys.argv) != 2:
        print("Usage: python client.py <magnet_link>")
        sys.exit(1)

    # Get the magnet link
    magnet_link = sys.argv[1]

    # Ensure download directory exists
    os.makedirs("./downloads", exist_ok=True)

    # Initialize libtorrent session
    ses = lt.session({'listen_interfaces': '0.0.0.0:6881'})

    # Add torrent using the magnet link
    params = lt.parse_magnet_uri(magnet_link)
    params.save_path = './downloads'
    handle = ses.add_torrent(params)

    # Wait for metadata
    while not handle.status().has_metadata:
        time.sleep(1)

    # Display initial download information
    s = handle.status()
    print(f"Downloading {s.name} ({s.total_wanted} bytes)")

    # Record start time for throughput calculation
    start_time = time.time()

    # Monitor download progress
    while handle.status().progress < 1.0:  # Exit when progress is 100%
        s = handle.status()
        print(f"\rProgress: {s.progress * 100:.2f}% "
              f"(down: {s.download_rate / 1000:.1f} kB/s, "
              f"peers: {s.num_peers})", end=' ')
        sys.stdout.flush()
        time.sleep(1)

    # Record end time
    end_time = time.time()

    # Indicate download completion
    print("\nDownload complete.")

    # Calculate client-side metrics
    s = handle.status()
    total_time = end_time - start_time
    client_payload_transferred = s.total_payload_download  # Actual file data downloaded
    client_total_data_transferred = s.total_download         # Total data including overhead
    client_overhead = client_total_data_transferred - client_payload_transferred
    client_throughput = client_payload_transferred / total_time if total_time > 0 else 0

    # Print client-side metrics
    print("\nClient Metrics:")
    print(f"  Payload Transferred: {client_payload_transferred} bytes")
    print(f"  Total Data Transferred: {client_total_data_transferred} bytes")
    print(f"  Overhead: {client_overhead} bytes")
    print(f"  Throughput: {client_throughput:.2f} bytes/second")

    # Cleanly pause and remove the session
    ses.pause()
    del ses
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    finally:
        # Remove the downloads folder on exit, regardless of exit status.
        print("\nDeleting downloads folder...")
        shutil.rmtree("./downloads", ignore_errors=True)