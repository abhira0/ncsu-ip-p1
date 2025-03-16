import requests
import time
import os
import click
import sys
from requests_toolbelt.utils import dump

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from utils import Statistics, ExperimentConfig, ResultsManager, ProgressDisplay

class HTTP11Client:
    def __init__(self, server_host, server_port=8000):
        self.server_host = server_host
        self.server_port = server_port
        self.server_url = f"http://{server_host}:{server_port}/"
        self.protocol_name = "HTTP/1.1"
    
    def download_file(self, file_name, timeout=30):
        start_time = time.time()
        url = f"{self.server_url}{file_name}"
        
        try:
            headers = {'Connection': 'close'}
            response = requests.get(url, stream=False, timeout=timeout, headers=headers)
            response.raise_for_status()
            
            end_time = time.time()
            transfer_time = end_time - start_time

            data = dump.dump_response(response)
            total_app_data = len(data)

            file_size = int(response.headers.get("Content-Length", 0))
            throughput = file_size * 8 / transfer_time if transfer_time > 0 else 0
            
            header_size = total_app_data - file_size
            overhead_ratio = total_app_data / file_size if file_size > 0 else 0
            
            return {
                'transfer_time': transfer_time,
                'throughput': throughput,
                'file_size': file_size,
                'total_app_data': total_app_data,
                'overhead_ratio': overhead_ratio,
                'header_size': header_size
            }
        
        except Exception as e:
            click.echo(click.style(f"\n❌ Error downloading {url}: {str(e)}", 
                                   fg='bright_red', bold=True))
            return None

    def run_experiment(self, file_name, repetitions):
        results = []
        
        with ProgressDisplay.create_progress_bar(file_name, repetitions) as bar:
            for i in bar:
                result = self.download_file(file_name)
                if result:
                    results.append(result)
        
        if not results:
            click.echo(click.style(f"❌ All download attempts failed for {file_name}", 
                                  fg='bright_red', bold=True))
            return None
        
        summary = Statistics.process_experiment_results(results, file_name)
        Statistics.print_experiment_summary(file_name, summary)
        return summary

    def run_experiments(self, server, file_prefix, experiments=None):
        if experiments is None:
            experiments = ExperimentConfig.get_default_experiments()
        
        results_data = ResultsManager.initialize_results(
            self.protocol_name, server, file_prefix
        )
        
        for exp in experiments:
            file_name = f"{file_prefix}_{exp['size']}"
            results = self.run_experiment(file_name, exp['repetitions'])
            if results:
                results_data["files"][file_name] = results
        
        return results_data


machine_config = ExperimentConfig.load_machine_config()

@click.command()
@click.option('--server', type=click.Choice(list(machine_config)), required=True, 
              help='Server to connect to')
@click.option('--file', type=click.Choice(['A', 'B']), required=True,
              help='File prefix to request (A or B)')
def main(server, file):
    server_ip = ExperimentConfig.get_server_ip(machine_config, server)
    client = HTTP11Client(server_ip)
    results_data = client.run_experiments(server, file)
    ResultsManager.save_results(results_data, "HTTP/1.1", file, server, current_dir)

main()