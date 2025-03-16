import libtorrent as lt
import time
import sys
import os
import shutil
import requests
import socket
import csv
from statistics import mean, stdev

def run_download(magnet_link, run_number, results):
    print(f"\n=== Starting download run {run_number} ===")
    download_path = "./downloads"
    os.makedirs(download_path, exist_ok=True)
    
    ses = lt.session({'listen_interfaces': '0.0.0.0:6881'})
    params = lt.parse_magnet_uri(magnet_link)
    params.save_path = download_path
    handle = ses.add_torrent(params)
    
    while not handle.status().has_metadata:
        time.sleep(1)
    
    s = handle.status()
    print(f"Downloading {s.name} ({s.total_wanted} bytes)")
    
    start_time = time.time()
    flag = False
    
    while handle.status().progress < 1.0:
        # if s.progress != 0.0 and not flag:
        #     start_time = time.time()
        #     flag = True
        s = handle.status()
        print(f"\rProgress: {s.progress * 100:.2f}% (down: {s.download_rate / 1000:.1f} kB/s, peers: {s.num_peers})", end=' ')
        sys.stdout.flush()
        
        time.sleep(1)
    
    end_time = time.time()
    print("\nDownload complete.")
    
    s = handle.status()
    total_time = end_time - start_time
    file_size = s.total_payload_download
    total_data_transferred = s.total_download
    # print(total_time, file_size, total_data_transferred)
    throughput = (file_size * 0.008) / total_time if total_time > 0 else 0
    overhead_file_ratio = total_data_transferred / file_size if file_size > 0 else 0
    
    print("\nClient Metrics:")
    print(f"  RTT: {total_time} seconds")
    print(f"  Throughput: {throughput:.2f} Mbps")
    print(f"  Total Data Transferred: {total_data_transferred} bytes")
    print(f"  Overhead File Ratio: {overhead_file_ratio:.2f}")
    
    results.append((total_time, throughput, total_data_transferred, overhead_file_ratio))
    
    ses.pause()
    del ses
    return end_time

def save_results(results, filename, runs):
    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["RTT", "Throughput", "TotalDataTransferred", "OverheadFileRatio"])
        writer.writerows(results)
    
    avg_rtt = mean([r[0] for r in results])
    avg_throughput = mean([r[1] for r in results])
    avg_total_data = mean([r[2] for r in results])
    avg_overhead_ratio = mean([r[3] for r in results])
    
    throughput_std_dev = stdev([r[1] for r in results]) if runs > 1 else 0
    summary = {
        "RTT": avg_rtt,
        "Throughput": avg_throughput,
        "TotalDataTransferred": avg_total_data,
        "OverheadFileRatio": avg_overhead_ratio,
        "Throughput_Std_Dev": throughput_std_dev
    }
    print("\nFinal Summary:", summary)

def main():
    ready_url = "http://192.168.98.129:8001/ready"
    if len(sys.argv) != 3:
        print("Usage: python client.py <magnet_link> <runs>")
        sys.exit(1)
    
    magnet_link = sys.argv[1]
    try:
        runs = int(sys.argv[2])
    except ValueError:
        print("Error: runs and file_size must be integers.")
        sys.exit(1)
    
    results = []
    
    for run in range(1, runs + 1):
        end_time = run_download(magnet_link, run, results)
        print("Sending ack to seeder...")
        resp = requests.post("http://192.168.98.129:8001/ack", json={"client": socket.gethostname(),"time":end_time})
        print(resp)
        
        while True:
            try:
                response = requests.get(ready_url, params={"client": socket.gethostname()})
                data = response.json()
                if data.get("ready", False):
                    break
            except requests.exceptions.JSONDecodeError:
                print("Received invalid JSON from /ready, retrying...")
            time.sleep(0.1)
        
        print("Deleting downloads folder...")
        shutil.rmtree("./downloads", ignore_errors=True)
        time.sleep(2)
    
    save_results(results, "download_results.csv", runs)

if __name__ == "__main__":
    try:
        main()
    finally:
        print("\nFinal cleanup: Deleting downloads folder...")
        shutil.rmtree("./downloads", ignore_errors=True)
