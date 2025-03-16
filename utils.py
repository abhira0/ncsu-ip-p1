import time
import os
import json
import math
import click
from statistics import mean, stdev

class Statistics:
    @staticmethod
    def calculate_statistics(values):
        n = len(values)
        if n == 0:
            return {"mean": 0, "stddev": 0}
        
        mean_val = sum(values) / n
        
        if n > 1:
            variance = sum((x - mean_val) ** 2 for x in values) / (n - 1)
            stddev = math.sqrt(variance)
        else:
            stddev = 0
        
        return {"mean": mean_val, "stddev": stddev}
    
    @staticmethod
    def process_experiment_results(results, file_name):
        if not results:
            return None
            
        transfer_times = [r['transfer_time'] for r in results]
        throughputs = [r['throughput'] for r in results]
        overhead_ratios = [r['overhead_ratio'] for r in results]
        
        time_stats = Statistics.calculate_statistics(transfer_times)
        throughput_stats = Statistics.calculate_statistics(throughputs)
        overhead_stats = Statistics.calculate_statistics(overhead_ratios)
        
        summary = {
            "file_name": file_name,
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
                "stddev": overhead_stats["stddev"]
            },
            "raw_results": results
        }
        
        return summary
    
    @staticmethod
    def print_experiment_summary(file_name, summary):
        click.echo(f"Avg transfer time:" + 
                  click.style(f" {summary['transfer_time']['mean']:.6f}s", fg="magenta") +
                  click.style(f" (±{summary['transfer_time']['stddev']:.6f})", fg='blue'))
        
        throughput_kb = summary['throughput_bps']['mean']/1024
        click.echo(f"Avg throughput:" + 
                  click.style(f" {throughput_kb:.2f} Kbps", fg="magenta") +
                  click.style(f" (±{summary['throughput_bps']['stddev']/1024:.2f})", fg='blue'))
        
        click.echo(f"Avg overhead ratio:" + 
                  click.style(f" {summary['overhead_ratio']['mean']:.6f}", fg="magenta") +
                  click.style(f" (±{summary['overhead_ratio']['stddev']:.6f})", fg='blue'))


class ExperimentConfig:
    @staticmethod
    def load_machine_config(config_path=None):
        if config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "machines.json")
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            click.echo(click.style(f"❌ Error loading machine configuration: {str(e)}", 
                                   fg='bright_red', bold=True))
            return None
    
    @staticmethod
    def get_server_ip(machine_config, server_name):
        server_ip = machine_config.get(server_name)
        if not server_ip:
            click.echo(click.style(f"❌ Unknown server: {server_name}. Use one of {list(machine_config.keys())}", 
                                  fg='bright_red', bold=True))
            return None
        return server_ip
    
    @staticmethod
    def get_default_experiments():
        return [
            {"size": "10kB", "repetitions": 1000},
            {"size": "100kB", "repetitions": 100},
            {"size": "1MB", "repetitions": 10},
            {"size": "10MB", "repetitions": 1}
        ]


class ResultsManager:
    @staticmethod
    def initialize_results(protocol, server, file_prefix):
        return {
            "protocol": protocol,
            "server": server,
            "file_prefix": file_prefix,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "files": {}
        }
    
    @staticmethod
    def save_results(results_data, protocol, file_prefix, server, output_dir=None):
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(__file__))
        
        result_filename = f"results_{file_prefix}_from_{server}_{protocol.replace('/', '')}.json"
        result_filepath = os.path.join(output_dir, result_filename)
        
        with open(result_filepath, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        click.echo(click.style(f"\nResults saved to {result_filepath}", 
                              fg='bright_green', bold=True))
        
        return result_filepath


class ProgressDisplay:
    @staticmethod
    def create_progress_bar(file_name, repetitions):
        click.echo("=" * 80)
        return click.progressbar(
            range(repetitions), 
            label=click.style(f'Downloading {file_name} x {repetitions}', fg='bright_green'),
            item_show_func=lambda i: f"Iteration {i+1}/{repetitions}" if i is not None else ""
        )