import requests
import time
import csv
import os
import logging
import json
import math
import click
from urllib.parse import urljoin
from requests_toolbelt.utils import dump

# ============================== 📡 CONFIG 📡 ==============================
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

# ============================== 📥 DOWNLOAD FUNCTIONS 📥 ==============================
def download_file(url, save_path, timeout=30):
    """Download a single file and measure performance metrics"""
    start_time = time.time()
    
    try:
        headers = {'Connection': 'close'}  # Ensure connection closes after each request
        response = requests.get(url, stream=False, timeout=timeout, headers=headers)
        response.raise_for_status()
        
        end_time = time.time()
        transfer_time = end_time - start_time

        data = dump.dump_response(response)
        total_app_data = len(data)

        file_size = int(response.headers["Content-Length"])
        throughput = file_size / transfer_time
        
        header_size = total_app_data - file_size
        overhead_ratio = total_app_data / file_size
        
        return {
            'transfer_time': transfer_time,
            'throughput': throughput,
            'file_size': file_size,
            'total_app_data': total_app_data,
            'overhead_ratio': overhead_ratio,
            'header_size': header_size
        }
    
    except Exception as e:
        logging.error(f"Error downloading {url}: {str(e)}")
        click.echo(click.style(f"❌ Error downloading {url}: {str(e)}", fg='bright_red', bold=True))
        return None

# ============================== 📊 ANALYSIS FUNCTIONS 📊 ==============================
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
    """Run a complete experiment for a specific file size with multiple repetitions"""
    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)
    
    results = []
    file_name = f"{file_prefix}_{file_size}"
    file_url = urljoin(server_url, file_name)
    
    logging.info(f"Starting experiment: {file_name} - {repetitions} repetitions")
    
    # Print section header
    click.echo("=" * 80)
    click.echo(click.style(f"EXPERIMENT: {file_name} - {repetitions} repetitions "))
    click.echo("=" * 40)
    
    success_count = 0
    with click.progressbar(
        range(repetitions), 
        label=click.style(f'Downloading {file_name}', fg='bright_green'),
        item_show_func=lambda i: f"Iteration {i+1}/{repetitions}" if i is not None else ""
    ) as bar:
        for i in bar:
            save_path = os.path.join(download_dir, f"{file_name}_{i}")
            result = download_file(file_url, save_path)
            
            if result:
                logging.info(f"Completed {i+1}/{repetitions} - Time: {result['transfer_time']:.6f}s, "
                             f"Throughput: {result['throughput']/1024:.2f} KB/s")
                
                results.append(result)
                success_count += 1
            else:
                click.echo(click.style(f"❌ Failed to download {file_url} on iteration {i+1}. Aborting experiment.", fg='bright_red', bold=True))
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
        
        # Show summary with fancy colors
        click.echo(f"Avg transfer time: {time_stats['mean']:.6f}s" + 
                  click.style(f" (±{time_stats['stddev']:.6f})", fg='blue'))
        
        # Color-code throughput based on speed
        throughput_kb = throughput_stats['mean']/1024
        click.echo(f"Avg throughput: {throughput_kb:.2f} KB/s" + 
                  click.style(f" (±{throughput_stats['stddev']/1024:.2f})", fg='blue'))
        
        click.echo(f"Avg overhead ratio: {overhead_stats['mean']:.6f}" + 
                  click.style(f" (±{overhead_stats['stddev']:.6f})", fg='blue'))
        
        return True
    
    return False

# ============================== 🚀 CLI COMMAND 🚀 ==============================
@click.command()
@click.option('--server', type=click.Choice(['vm1', 'vm2']), required=True, 
              help='Server to connect to (vm1 or vm2)')
@click.option('--file', type=click.Choice(['A', 'B']), required=True,
              help='File prefix to request (A or B)')
def main(server, file):
    """HTTP/1.1 Client for Protocol Testing

    This tool performs download experiments using HTTP/1.1 protocol.
    It tests different file sizes with multiple repetitions to gather
    performance metrics like throughput, transfer time, and overhead ratio.
    """
    
    server_ip = VM_IP_MAP.get(server)
    if not server_ip:
        logging.error(f"Unknown server: {server}. Use vm1 or vm2.")
        click.echo(click.style(f"❌ Unknown server: {server}. Use vm1 or vm2.", fg='bright_red', bold=True))
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
        "server": server,
        "file_prefix": file,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": {}
    }
    
    # Run all experiments
    for exp in experiments:
        run_experiment(
            server_url, 
            file, 
            exp["size"], 
            exp["repetitions"],
            results_data["files"]
        )
    
    # Write consolidated results to a single JSON file
    result_filename = f"results_{file}_from_{server}_http1.json"
    with open(result_filename, 'w') as f:
        json.dump(results_data, f, indent=2)
    
if __name__ == '__main__':
    main()