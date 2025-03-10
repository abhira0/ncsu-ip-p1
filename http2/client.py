#!/usr/bin/env python3
"""
Simple HTTP/2-compatible client for CSC/ECE 573 Project #1
Non-SSL version for faster testing
"""

import requests
import time
import json
import os
import sys
import argparse
import statistics

cur_file_path = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(cur_file_path, "..", "machines.json"), 'r') as f:
    MACHINE_IP_MAP = json.load(f)

def download_file(url, output=None):
    """Download a file using HTTP/2 headers and measure performance"""
    headers = {
        'Connection': 'Upgrade, HTTP2-Settings',
        'Upgrade': 'h2c',
        'HTTP2-Settings': 'AAMAAABkAAQAAP__',
    }
    
    start_time = time.time()
    
    try:
        # Use regular HTTP
        response = requests.get(url, headers=headers, stream=True)
        
        # Get content data
        data = response.content
        
        end_time = time.time()
        
        # Calculate metrics
        content_length = int(response.headers.get('Content-Length', len(data)))
        header_size = sum(len(f"{k}: {v}\r\n".encode()) for k, v in response.headers.items())
        total_bytes = content_length + header_size
        duration = end_time - start_time
        throughput = content_length / duration if duration > 0 else 0
        overhead_ratio = total_bytes / content_length if content_length > 0 else 0
        
        result = {
            "duration_seconds": duration,
            "throughput_bytes_per_second": throughput,
            "content_length_bytes": content_length,
            "header_size_bytes": header_size,
            "overhead_ratio": overhead_ratio,
        }
        
        # Save output if requested
        if output:
            with open(output, "wb") as f:
                f.write(data)
        
        return result
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        sys.exit(1)

def run_experiment(server_ip, file_prefix, file_size, repetitions):
    """Run a download experiment for a specific file size with multiple repetitions"""
    file_name = f"{file_prefix}_{file_size}"
    # Using HTTP instead of HTTPS and port 8000
    url = f"http://{server_ip}:8000/{file_name}"
    
    print(f"\nDownloading {file_name} {repetitions} times...")
    
    results = []
    
    for i in range(repetitions):
        sys.stdout.write(f"\rIteration {i+1}/{repetitions}")
        sys.stdout.flush()
        
        result = download_file(url)
        results.append(result)
    
    # Calculate averages
    durations = [r["duration_seconds"] for r in results]
    throughputs = [r["throughput_bytes_per_second"] for r in results]
    overheads = [r["overhead_ratio"] for r in results]
    
    avg_duration = statistics.mean(durations)
    avg_throughput = statistics.mean(throughputs)
    avg_overhead = statistics.mean(overheads)
    
    # Calculate standard deviations (if more than one sample)
    if len(durations) > 1:
        stdev_duration = statistics.stdev(durations)
        stdev_throughput = statistics.stdev(throughputs)
        stdev_overhead = statistics.stdev(overheads)
    else:
        stdev_duration = 0
        stdev_throughput = 0
        stdev_overhead = 0
    
    print(f"\n{file_name} - Average results:")
    print(f"  Duration: {avg_duration:.6f} seconds (±{stdev_duration:.6f})")
    print(f"  Throughput: {avg_throughput/1024:.2f} KB/s (±{stdev_throughput/1024:.2f})")
    print(f"  Overhead ratio: {avg_overhead:.6f} (±{stdev_overhead:.6f})")
    
    return {
        "file_name": file_name,
        "repetitions_completed": repetitions,
        "content_length_bytes": results[0]["content_length_bytes"],
        "transfer_time": {
            "mean": avg_duration,
            "stddev": stdev_duration
        },
        "throughput_bps": {
            "mean": avg_throughput,
            "stddev": stdev_throughput
        },
        "overhead_ratio": {
            "mean": avg_overhead,
            "stddev": stdev_overhead
        },
        "raw_results": results
    }

def main():
    parser = argparse.ArgumentParser(description="HTTP/2 Client for Project #1")
    parser.add_argument("--server", choices=["vm1", "vm2"], required=True, 
                       help="Server to connect to (vm1 or vm2)")
    parser.add_argument("--file", choices=["A", "B"], required=True,
                       help="File prefix to request (A or B)")
    args = parser.parse_args()
    
    # Load machine IPs
    server_ip = MACHINE_IP_MAP.get(args.server)
    
    if not server_ip:
        print(f"Error: IP for server '{args.server}' not found in machines.json")
        sys.exit(1)
    
    # Define experiments
    experiments = [
        {"size": "10kB", "repetitions": 1000},
        {"size": "100kB", "repetitions": 100},
        {"size": "1MB", "repetitions": 10},
        {"size": "10MB", "repetitions": 1}
    ]
    
    # Run experiments
    all_results = {
        "protocol": "HTTP/2",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "server": args.server,
        "server_ip": server_ip,
        "file_prefix": args.file,
        "files": {}
    }
    
    for exp in experiments:
        result = run_experiment(server_ip, args.file, exp["size"], exp["repetitions"])
        all_results["files"][result["file_name"]] = result
    
    # Save results to file
    output_file = f"results_{args.file}_from_{args.server}_http2.json"
    with open(os.path.join(cur_file_path, output_file), "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\nResults saved to {output_file}")

if __name__ == "__main__":
    main()