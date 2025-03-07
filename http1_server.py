import requests
import time
import csv
import os
import logging
import argparse
import json
import math
from urllib.parse import urljoin

# IP address mapping
VM_IP_MAP = {
    "vm1": "192.168.254.129",
    "vm2": "192.168.254.130"
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='http_client.log'
)

def download_file(url, save_path, timeout=30):
    total_bytes = 0
    start_time = time.time()
    
    try:
        headers = {'Connection': 'close'}  # Ensure connection closes after each request
        response = requests.get(url, stream=True, timeout=timeout, headers=headers)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    total_bytes += len(chunk)
        
        end_time = time.time()
        transfer_time = end_time - start_time
        
        # Calculate throughput (bytes per second)
        file_size = os.path.getsize(save_path)
        throughput = file_size / transfer_time
        
        # Total application layer data (including headers)
        header_size = sum(len(k) + len(v) for k, v in response.request.headers.items())
        response_header_size = sum(len(k) + len(v) for k, v in response.headers.items())
        total_app_data = total_bytes + header_size + response_header_size
        
        # Calculate overhead ratio (total app data / file size)
        overhead_ratio = total_app_data / file_size
        
        return {
            'transfer_time': transfer_time,
            'throughput': throughput,
            'file_size': file_size,
            'total_app_data': total_app_data,
            'overhead_ratio': overhead_ratio,
            'header_size': header_size + response_header_size
        }
    
    except Exception as e:
        logging.error(f"Error downloading {url}: {str(e)}")
        print(f"Error downloading {url}: {str(e)}")
        return None

def calculate_statistics(values):
    """Calculate mean and standard deviation for a list of values"""
    n = len(values)
    if n == 0:
        return {"mean": 0, "stddev": 0}
    
    mean = sum(values) / n
    
    # Calculate standard deviation
    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0
    
    return {"mean": mean, "stddev": stddev}

def run_experiment(server_url, file_prefix, file_size, repetitions, results_data):
    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)
    
    results = []
    file_name = f"{file_prefix}_{file_size}"
    file_url = urljoin(server_url, file_name)
    
    logging.info(f"Starting experiment: {file_name} - {repetitions} repetitions")
    print(f"Starting experiment: {file_name} - {repetitions} repetitions")
    print(f"Downloading from: {file_url}")
    
    for i in range(repetitions):
        save_path = os.path.join(download_dir, f"{file_name}_{i}")
        result = download_file(file_url, save_path)
        
        if result:
            logging.info(f"Completed {i+1}/{repetitions} - Time: {result['transfer_time']:.6f}s, "
                         f"Throughput: {result['throughput']/1024:.2f} KB/s")
            
            if (i+1) % 10 == 0 or repetitions <= 10:
                print(f"Completed {i+1}/{repetitions} - Time: {result['transfer_time']:.6f}s, "
                      f"Throughput: {result['throughput']/1024:.2f} KB/s")
            
            results.append(result)
        else:
            print(f"Failed to download {file_url} on iteration {i+1}. Aborting experiment.")
            logging.error(f"Failed to download {file_url} on iteration {i+1}. Aborting experiment.")
            break
    
    # Only calculate statistics if we have results
    if results:
        # Extract lists of values for statistical analysis
        transfer_times = [r['transfer_time'] for r in results]
        throughputs = [r['throughput'] for r in results]
        overhead_ratios = [r['overhead_ratio'] for r in results]
        
        # Calculate statistics
        time_stats = calculate_statistics(transfer_times)
        throughput_stats = calculate_statistics(throughputs)
        overhead_stats = calculate_statistics(overhead_ratios)
        
        # Store result in the results_data dictionary
        results_data[file_name] = {
            "file_size_bytes": results[0]['file_size'],
            "repetitions_completed": len(results),
            "transfer_time": {
                "mean": time_stats["mean"],
                "stddev": time_stats["stddev"]
            },
            "throughput_bps": {
                "mean": throughput_stats["mean"],
                "stddev": throughput_stats["stddev"]
            },
            "overhead_ratio": {
                "mean": overhead_stats["mean"],
                "stddev": overhead_stats["stddev"],
                "description": "Total application layer data / file size"
            },
            "raw_results": results  # Include all raw results for detailed analysis if needed
        }
        
        print(f"Experiment completed for {file_name}:")
        print(f"  Avg transfer time: {time_stats['mean']:.6f}s (±{time_stats['stddev']:.6f})")
        print(f"  Avg throughput: {throughput_stats['mean']/1024:.2f} KB/s (±{throughput_stats['stddev']/1024:.2f})")
        print(f"  Avg overhead ratio: {overhead_stats['mean']:.6f} (±{overhead_stats['stddev']:.6f})")
        
        return True
    
    return False

def run_all_experiments(server, file_prefix):
    server_ip = VM_IP_MAP.get(server)
    if not server_ip:
        logging.error(f"Unknown server: {server}. Use vm1 or vm2.")
        print(f"Unknown server: {server}. Use vm1 or vm2.")
        return
    
    server_url = f"http://{server_ip}:8000/"
    
    experiments = [
        {"size": "10kB", "repetitions": 1000},
        {"size": "100kB", "repetitions": 100},
        {"size": "1MB", "repetitions": 10},
        {"size": "10MB", "repetitions": 1}
    ]
    
    # Create a single results data structure
    results_data = {
        "protocol": "HTTP/1.1",
        "client": f"VM{'1' if server == 'vm2' else '2'}",
        "server": server,
        "file_prefix": file_prefix,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": {}
    }
    
    for exp in experiments:
        run_experiment(
            server_url, 
            file_prefix, 
            exp["size"], 
            exp["repetitions"],
            results_data["files"]
        )
    
    # Write consolidated results to a single JSON file
    result_filename = f"results_{file_prefix}_from_{server}_http1.json"
    with open(result_filename, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"\nAll experiments completed. Results saved to {result_filename}")
    
    # Generate a summary CSV as well for easier import into Excel
    summary_csv = f"summary_{file_prefix}_from_{server}_http1.csv"
    with open(summary_csv, 'w', newline='') as csvfile:
        fieldnames = ['file_name', 'file_size_bytes', 'repetitions', 
                     'mean_transfer_time', 'stddev_transfer_time',
                     'mean_throughput_bps', 'stddev_throughput_bps',
                     'mean_overhead_ratio', 'stddev_overhead_ratio']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for file_name, data in results_data["files"].items():
            writer.writerow({
                'file_name': file_name,
                'file_size_bytes': data['file_size_bytes'],
                'repetitions': data['repetitions_completed'],
                'mean_transfer_time': data['transfer_time']['mean'],
                'stddev_transfer_time': data['transfer_time']['stddev'],
                'mean_throughput_bps': data['throughput_bps']['mean'],
                'stddev_throughput_bps': data['throughput_bps']['stddev'],
                'mean_overhead_ratio': data['overhead_ratio']['mean'],
                'stddev_overhead_ratio': data['overhead_ratio']['stddev']
            })
    
    print(f"Summary CSV saved to {summary_csv}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='HTTP/1.1 Client for Protocol Testing')
    parser.add_argument('--server', choices=['vm1', 'vm2'], required=True, 
                        help='Server to connect to (vm1 or vm2)')
    parser.add_argument('--file', choices=['A', 'B'], required=True,
                        help='File prefix to request (A or B)')
    args = parser.parse_args()
    
    run_all_experiments(args.server, args.file)