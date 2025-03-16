import socket
import time
import os
import sys
import click
import h2.connection
import h2.config
import h2.events
import h2.settings

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from utils import Statistics, ExperimentConfig, ResultsManager, ProgressDisplay

class HTTP2Client:
    def __init__(self, server_host, server_port=8000):
        self.server_host = server_host
        self.server_port = server_port
        self.connection = None
        self.socket = None
        self.protocol_name = "HTTP/2"

    def open_connection(self):
        try:
            socket.setdefaulttimeout(15)
            
            self.socket = socket.create_connection((self.server_host, self.server_port))
            
            self.connection = h2.connection.H2Connection()
            self.connection.local_settings = h2.settings.Settings(
                client=True,
                initial_values = {
                    h2.settings.SettingCodes.MAX_CONCURRENT_STREAMS: 2**31 - 1
                }
            )
            
            self.connection.initiate_connection()
            self.socket.sendall(self.connection.data_to_send())
            
            return True
            
        except Exception as e:
            click.echo(click.style(
                f"\n❌ Error connecting to {self.server_host}:{self.server_port}: {str(e)}", 
                fg='bright_red', bold=True
            ))
            return False

    def close_connection(self):
        if self.connection and self.socket:
            try:
                self.connection.close_connection()
                self.socket.sendall(self.connection.data_to_send())
                self.socket.close()
            except Exception as e:
                click.echo(f"Warning: Error closing connection: {e}")
            
            self.connection = None
            self.socket = None

    def download_file(self, file_name):
        if not self.connection or not self.socket:
            click.echo(click.style("Error: Connection not open", fg='bright_red'))
            return None
        
        start_time = time.time()
        
        try:
            headers = [
                (":method", "GET"),
                (":scheme", "http"),
                (":authority", f"{self.server_host}:{self.server_port}"),
                (":path", f"/{file_name}"),
                ("accept", "*/*"),
            ]
            
            stream_id = self.connection.get_next_available_stream_id()
            self.connection.send_headers(stream_id, headers)
            self.socket.sendall(self.connection.data_to_send())
            
            response_ended = False
            header_data_size = 0
            received_data = b""
            
            while not response_ended:
                data = self.socket.recv(65536 * 1024)
                if not data:
                    break
                
                events = self.connection.receive_data(data)
                for event in events:
                    if isinstance(event, h2.events.ResponseReceived):
                        header_data_size = sum(len(name) + len(value) for name, value in event.headers)
                    
                    if isinstance(event, h2.events.DataReceived):
                        received_data += event.data
                        
                        self.connection.acknowledge_received_data(
                            event.flow_controlled_length, event.stream_id
                        )
                    
                    if isinstance(event, h2.events.StreamEnded):
                        response_ended = True
                        break
                
                self.socket.sendall(self.connection.data_to_send())
            
            end_time = time.time()
            transfer_time = end_time - start_time
            
            file_size = len(received_data)
            
            framing_overhead = 18
            total_app_data = header_data_size + file_size + framing_overhead
            overhead_ratio = total_app_data / file_size if file_size > 0 else 0
            
            throughput = (file_size * 8) / transfer_time if transfer_time > 0 else 0
            
            return {
                'transfer_time': transfer_time,
                'file_size': file_size,
                'throughput': throughput,
                'total_app_data': total_app_data,
                'overhead_ratio': overhead_ratio
            }
            
        except Exception as e:
            click.echo(click.style(f"\n❌ Error downloading {file_name}: {str(e)}", 
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
        
        if not self.open_connection():
            return results_data
        
        try:
            for exp in experiments:
                file_name = f"{file_prefix}_{exp['size']}"
                results = self.run_experiment(file_name, exp['repetitions'])
                
                if results:
                    results_data["files"][file_name] = results
                
        finally:
            self.close_connection()
        
        return results_data


machine_config = ExperimentConfig.load_machine_config()


@click.command()
@click.option('--server', type=click.Choice(list(machine_config)), required=True, 
              help='Server to connect to')
@click.option('--file', type=click.Choice(['A', 'B']), required=True,
              help='File prefix to request (A or B)')
def main(server, file):
    server_ip = ExperimentConfig.get_server_ip(machine_config, server)
    client = HTTP2Client(server_ip)
    results_data = client.run_experiments(server, file)
    ResultsManager.save_results(results_data, "HTTP/2", file, server, current_dir)

main()