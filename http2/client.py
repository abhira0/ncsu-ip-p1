#!/usr/bin/env python3
"""
HTTP/2 Cleartext (h2c) client using h2 module for CSC/ECE 573 Project #1
Non-SSL version for faster testing
"""

import socket
import json
import time
import os
import sys
import argparse
import logging
import statistics
from h2.connection import H2Connection
from h2.config import H2Configuration
from h2.events import (
    ResponseReceived, DataReceived, StreamEnded,
    StreamReset, SettingsAcknowledged,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('h2c_client')

cur_file_path = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(cur_file_path, "..", "machines.json"), 'r') as f:
    MACHINE_IP_MAP = json.load(f)

def download_file(host, port, path):
    """Download a file using HTTP/2 Cleartext (h2c) and measure performance"""
    start_time = time.time()
    
    # Create socket
    sock = socket.socket()
    sock.settimeout(10)  # Set timeout
    
    # Connect to server
    try:
        sock.connect((host, port))
    except socket.error as e:
        logger.error(f"Connection error: {e}")
        return None
    
    # Create HTTP/2 connection
    config = H2Configuration(client_side=True)
    conn = H2Connection(config=config)
    conn.initiate_connection()
    
    # Send the preamble
    sock.sendall(conn.data_to_send())
    
    # Send the request
    stream_id = conn.get_next_available_stream_id()
    headers = [
        (':method', 'GET'),
        (':path', f'/{path}'),
        (':authority', f'{host}:{port}'),
        (':scheme', 'http'),
        ('user-agent', 'python-h2'),
    ]
    conn.send_headers(stream_id, headers, end_stream=True)
    sock.sendall(conn.data_to_send())
    
    # Receive the response
    response_data = b''
    header_size = 0
    content_length = 0
    response_received = False
    stream_ended = False
    
    while not stream_ended:
        try:
            data = sock.recv(65535)
            if not data:
                break
                
            events = conn.receive_data(data)
            
            for event in events:
                if isinstance(event, ResponseReceived):
                    # Record headers size and content length
                    for header, value in event.headers:
                        header_size += len(header) + len(value) + 2  # +2 for colon and space
                        if header == b'content-length':
                            content_length = int(value.decode())
                    response_received = True
                
                elif isinstance(event, DataReceived):
                    # Append response data
                    response_data += event.data
                
                elif isinstance(event, StreamEnded):
                    # Stream ended
                    stream_ended = True
                
                elif isinstance(event, StreamReset):
                    logger.error(f"Stream reset by server: {event.error_code}")
                    break
                
                elif isinstance(event, SettingsAcknowledged):
                    pass  # Nothing to do here
            
            # Send any pending data
            pending_data = conn.data_to_send()
            if pending_data:
                sock.sendall(pending_data)
        
        except socket.error as e:
            logger.error(f"Error during download: {e}")
            break
    
    # Close the connection
    sock.close()
    
    end_time = time.time()
    
    # Calculate metrics
    if response_received and response_data:
        duration = end_time - start_time
        throughput = len(response_data) / duration if duration > 0 else 0
        overhead_ratio = (len(response_data) + header_size) / len(response_data) if len(response_data) > 0 else 0
        
        return {
            "duration_seconds": duration,
            "throughput_bytes_per_second": throughput,
            "content_length_bytes": len(response_data),
            "header_size_bytes": header_size,
            "overhead_ratio": overhead_ratio,
        }
    
    return None

def run_experiment(server_ip, file_prefix, file_size, repetitions):
    """Run a download experiment for a specific file size with multiple repetitions"""
    file_name = f"{file_prefix}_{file_size}"
    
    print(f"\nDownloading {file_name} {repetitions} times...")
    
    results = []
    
    for i in range(repetitions):
        sys.stdout.write(f"\rIteration {i+1}/{repetitions}")
        sys.stdout.flush()
        
        result = download_file(server_ip, 8000, file_name)
        if result:
            results.append(result)
        else:
            print(f"\nError in iteration {i+1}, skipping...")
    
    if not results:
        print(f"All download attempts failed for {file_name}")
        return None
    
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
        "repetitions_completed": len(results),
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
    parser = argparse.ArgumentParser(description="HTTP/2 Cleartext Client for Project #1")
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
        if result:
            all_results["files"][result["file_name"]] = result
    
    # Save results to file
    output_file = f"results_{args.file}_from_{args.server}_http2.json"
    with open(os.path.join(cur_file_path, output_file), "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\nResults saved to {output_file}")

if __name__ == "__main__":
    main()