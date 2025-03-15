import socket
import time
import os
import json
import math
import click
import h2.connection
import h2.config
import h2.events
import h2.settings
from statistics import mean, stdev
from collections import defaultdict

class HTTP2Client:
    """HTTP/2 client for downloading files and measuring performance."""
    
    def __init__(self, server_host, server_port):
        """Initialize the HTTP/2 client with server host and port."""
        self.server_host = server_host
        self.server_port = server_port
        self.connection = None
        self.socket = None

    def open_connection(self):
        """Open a connection to the server."""
        try:
            # Set a default timeout for the socket
            socket.setdefaulttimeout(15)
            
            # Create socket and connect to the server
            self.socket = socket.create_connection((self.server_host, self.server_port))
            
            # Set up HTTP/2 connection
            self.connection = h2.connection.H2Connection()
            self.connection.local_settings = h2.settings.Settings(
                client=True,
                initial_values = {
                    h2.settings.SettingCodes.MAX_CONCURRENT_STREAMS: 2**31 - 1
                }
            )
            
            # Initialize the connection
            self.connection.initiate_connection()
            self.socket.sendall(self.connection.data_to_send())
            
            return True
            
        except Exception as e:
            click.echo(click.style(f"\n❌ Error connecting to {self.server_host}:{self.server_port}: {str(e)}", fg='bright_red', bold=True))
            return False

    def close_connection(self):
        """Close the HTTP/2 connection."""
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
        """Download a single file and measure performance metrics."""
        if not self.connection or not self.socket:
            click.echo(click.style("Error: Connection not open", fg='bright_red'))
            return None
        
        # Remove the file if it already exists locally
        if os.path.exists(file_name):
            try:
                os.remove(file_name)
            except Exception as e:
                click.echo(f"Warning: Could not remove existing file {file_name}: {e}")
        
        start_time = time.time()
        
        try:
            # Define the request headers
            headers = [
                (":method", "GET"),
                (":scheme", "http"),
                (":authority", f"{self.server_host}:{self.server_port}"),
                (":path", f"/{file_name}"),
                ("accept", "*/*"),
            ]
            
            # Get a stream ID and send the request
            stream_id = self.connection.get_next_available_stream_id()
            self.connection.send_headers(stream_id, headers)
            self.socket.sendall(self.connection.data_to_send())
            
            # Process the response
            response_ended = False
            header_data_size = 0
            received_data = b""
            
            while not response_ended:
                # Receive data from the server
                data = self.socket.recv(65536 * 1024)
                if not data:
                    break
                
                # Process HTTP/2 events
                events = self.connection.receive_data(data)
                for event in events:
                    if isinstance(event, h2.events.ResponseReceived):
                        # Get the size of the headers
                        header_data_size = sum(len(name) + len(value) for name, value in event.headers)
                    
                    if isinstance(event, h2.events.DataReceived):
                        # Accumulate received data
                        received_data += event.data
                        
                        # Acknowledge the data to manage flow control
                        self.connection.acknowledge_received_data(
                            event.flow_controlled_length, event.stream_id
                        )
                    
                    if isinstance(event, h2.events.StreamEnded):
                        # Mark the response as complete
                        response_ended = True
                        break
                
                # Send any pending data (like acknowledgments)
                self.socket.sendall(self.connection.data_to_send())
            
            # Calculate metrics
            end_time = time.time()
            transfer_time = end_time - start_time
            
            # Get the actual file size
            file_size = len(received_data)
            
            # Calculate overhead (header size plus HTTP/2 framing overhead estimate)
            # The 18 bytes is an estimate of HTTP/2 frame overhead
            framing_overhead = 18
            total_application_data = header_data_size + file_size + framing_overhead
            overhead_ratio = total_application_data / file_size if file_size > 0 else 0
            
            # Calculate throughput in bits per second
            throughput = (file_size * 8) / transfer_time if transfer_time > 0 else 0
            
            return {
                'transfer_time': transfer_time,
                'file_size': file_size,
                'throughput': throughput,
                'total_application_data': total_application_data,
                'overhead_ratio': overhead_ratio
            }
            
        except Exception as e:
            click.echo(click.style(f"\n❌ Error downloading {file_name}: {str(e)}", fg='bright_red', bold=True))
            return None

    def run_experiment(self, file_name, repetitions):
        """Run an experiment with the specified file and number of repetitions."""
        results = []
        total_repetitions = repetitions
        
        # Display header for this experiment
        click.echo("=" * 80)
        click.echo(click.style(f"Experiment: {file_name} x {repetitions} repetitions", fg='bright_blue', bold=True))
        
        # Create progress bar
        with click.progressbar(
            length=repetitions,
            label=click.style(f'Downloading {file_name}', fg='bright_green'),
            item_show_func=lambda _: f"Iteration {len(results)+1}/{repetitions}"
        ) as bar:
            for i in range(repetitions):
                # Download the file and get metrics
                result = self.download_file(file_name)
                
                if result:
                    results.append(result)
                    bar.update(1)
                else:
                    click.echo(click.style(f"\nFailed attempt {i+1}", fg='bright_red'))
        
        # Check if we got any results
        if not results:
            click.echo(click.style(f"❌ All download attempts failed for {file_name}", fg='bright_red', bold=True))
            return None
        
        # Calculate statistics
        transfer_times = [r['transfer_time'] for r in results]
        throughputs = [r['throughput'] for r in results]
        overhead_ratios = [r['overhead_ratio'] for r in results]
        
        # Calculate mean and standard deviation
        time_mean = mean(transfer_times)
        throughput_mean = mean(throughputs)
        overhead_mean = mean(overhead_ratios)
        
        # Only calculate standard deviation if we have more than one sample
        time_stddev = stdev(transfer_times) if len(transfer_times) > 1 else 0
        throughput_stddev = stdev(throughputs) if len(throughputs) > 1 else 0
        overhead_stddev = stdev(overhead_ratios) if len(overhead_ratios) > 1 else 0
        
        # Compile the results
        summary = {
            "file_name": file_name,
            "file_size_bytes": results[0]['file_size'],
            "repetitions_requested": repetitions,
            "repetitions_completed": len(results),
            "transfer_time_seconds": {
                "mean": time_mean,
                "stddev": time_stddev
            },
            "throughput_bps": {
                "mean": throughput_mean,
                "stddev": throughput_stddev
            },
            "overhead_ratio": {
                "mean": overhead_mean,
                "stddev": overhead_stddev
            },
            "raw_results": results
        }
        
        # Display summary
        click.echo(f"\nSummary for {file_name}:")
        click.echo(f"  Average transfer time: {time_mean:.6f} seconds (±{time_stddev:.6f})")
        click.echo(f"  Average throughput: {throughput_mean/1000000:.2f} Mbps (±{throughput_stddev/1000000:.2f})")
        click.echo(f"  Average overhead ratio: {overhead_mean:.6f} (±{overhead_stddev:.6f})")
        
        return summary

def calculate_statistics(values):
    """Calculate mean and standard deviation for a list of values."""
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

@click.command()
@click.option('--server', type=click.Choice(['vm1', 'vm2']), required=True, 
              help='Server to connect to (vm1 or vm2)')
@click.option('--file', type=click.Choice(['A', 'B']), required=True,
              help='File prefix to request (A or B)')
def main(server, file):
    """Run HTTP/2 file transfer experiments."""
    # Load machine configuration
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "machines.json"), 'r') as f:
            machine_ip_map = json.load(f)
        
        server_ip = machine_ip_map.get(server)
        if not server_ip:
            click.echo(click.style(f"❌ Unknown server: {server}. Use vm1 or vm2.", fg='bright_red', bold=True))
            return
    except Exception as e:
        click.echo(click.style(f"❌ Error loading machine configuration: {str(e)}", fg='bright_red', bold=True))
        return
    
    # Define experiments with file sizes and repetitions
    experiments = [
        {"size": "10kB", "repetitions": 1000},
        {"size": "100kB", "repetitions": 100},
        {"size": "1MB", "repetitions": 10},
        {"size": "10MB", "repetitions": 1}
    ]
    
    # Initialize results data structure
    results_data = {
        "protocol": "HTTP/2",
        "server": server,
        "file_prefix": file,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": {}
    }
    
    # Create the client
    client = HTTP2Client(server_ip, 8000)
    
    # Open the connection
    if not client.open_connection():
        return
    
    try:
        # Run each experiment
        for exp in experiments:
            file_name = f"{file}_{exp['size']}"
            results = client.run_experiment(file_name, exp['repetitions'])
            
            if results:
                results_data["files"][file_name] = results
    finally:
        # Make sure to close the connection
        client.close_connection()
    
    # Save the results to a file
    result_filename = f"results_{file}_from_{server}_http2.json"
    result_filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), result_filename)
    
    with open(result_filepath, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    click.echo(click.style(f"\nResults saved to {result_filepath}", fg='bright_green', bold=True))

if __name__ == '__main__':
    main()