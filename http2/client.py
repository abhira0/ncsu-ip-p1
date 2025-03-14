import httpx
import time
import os
import json
import math
import click
import asyncio

cur_file_path = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(cur_file_path, "..", "machines.json"), 'r') as f:
    MACHINE_IP_MAP = json.load(f)

async def download_file(client, url, timeout=30):
    """Download a single file and measure performance metrics"""
    start_time = time.time()
    
    try:
        response = await client.get(url, timeout=timeout)
        response.raise_for_status()
        content = response.read()
        
        end_time = time.time()
        transfer_time = end_time - start_time

        file_size = int(response.headers.get("Content-Length", len(content)))
        throughput = file_size / transfer_time
        
        # Calculate approximate header size and overhead
        headers_str = str(response.headers)
        header_size = len(headers_str.encode('utf-8'))
        total_app_data = file_size + header_size
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
        click.echo(click.style(f"\n❌ Error downloading {url}: {str(e)}", fg='bright_red', bold=True))
        raise

def calculate_statistics(values):
    """Calculate mean and standard deviation for a list of values"""
    n = len(values)
    if n == 0:
        return {"mean": 0, "stddev": 0}
    
    mean = sum(values) / n
    
    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0
    
    return {"mean": mean, "stddev": stddev}

async def run_experiment(client, server_url, file_prefix, file_size, repetitions, results_data):
    """Run a complete experiment for a specific file size with multiple repetitions"""
    results = []
    file_name = f"{file_prefix}_{file_size}"
    file_url = f"{server_url}/{file_name}"
    
    click.echo("=" * 80)
    with click.progressbar(
        range(repetitions), 
        label=click.style(f'Downloading {file_name} x {repetitions}', fg='bright_green'),
        item_show_func=lambda i: f"Iteration {i+1}/{repetitions}" if i is not None else ""
    ) as bar:
        for i in bar:
            result = await download_file(client, file_url)
            results.append(result)
            bar.update(1)
    
    if results:
        transfer_times = [r['transfer_time'] for r in results]
        throughputs = [r['throughput'] for r in results]
        overhead_ratios = [r['overhead_ratio'] for r in results]
        
        time_stats = calculate_statistics(transfer_times)
        throughput_stats = calculate_statistics(throughputs)
        overhead_stats = calculate_statistics(overhead_ratios)
        
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
            "raw_results": results
        }
        
        click.echo(f"Avg transfer time:" + click.style(f" {time_stats['mean']:.6f}s", fg="magenta") +
                  click.style(f" (±{time_stats['stddev']:.6f})", fg='blue'))
        
        throughput_kb = throughput_stats['mean']/1024
        click.echo(f"Avg throughput:" + click.style(f" {throughput_kb:.2f} KB/s", fg="magenta") +
                  click.style(f" (±{throughput_stats['stddev']/1024:.2f})", fg='blue'))
        
        click.echo(f"Avg overhead ratio:" + click.style(f" {overhead_stats['mean']:.6f}", fg="magenta") +
                  click.style(f" (±{overhead_stats['stddev']:.6f})", fg='blue'))
        
        return True
    
    return False

@click.command()
@click.option('--server', type=click.Choice(['vm1', 'vm2']), required=True, 
              help='Server to connect to (vm1 or vm2)')
@click.option('--file', type=click.Choice(['A', 'B']), required=True,
              help='File prefix to request (A or B)')
async def main(server, file):
    server_ip = MACHINE_IP_MAP.get(server)
    if not server_ip:
        click.echo(click.style(f"❌ Unknown server: {server}. Use vm1 or vm2.", fg='bright_red', bold=True))
        return
    
    server_url = f"https://{server_ip}:8001"

    experiments = [
        {"size": "10kB", "repetitions": 1000},
        {"size": "100kB", "repetitions": 100},
        {"size": "1MB", "repetitions": 10},
        {"size": "10MB", "repetitions": 1}
    ]
    
    results_data = {
        "protocol": "HTTP/2",
        "server": server,
        "file_prefix": file,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": {}
    }
    
    # HTTP/2 requires TLS, but we'll skip certificate verification for local testing
    async with httpx.AsyncClient(http2=True, verify=False) as client:
        for exp in experiments:
            await run_experiment(
                client,
                server_url, 
                file, 
                exp["size"], 
                exp["repetitions"],
                results_data["files"]
            )
    
    result_filename = f"results_{file}_from_{server}_http2.json"
    with open(os.path.join(cur_file_path, result_filename), 'w') as f:
        json.dump(results_data, f, indent=2)

if __name__ == '__main__':
    asyncio.run(main())