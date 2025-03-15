import http.server
import socketserver
import socket
import os
import sys
import json
import click
import h2.connection
import h2.config
import h2.events
import h2.settings

class HTTP2Server:
    """HTTP/2 server implementation that serves files from a directory."""
    
    def __init__(self, host, port, files_dir):
        """Initialize the HTTP/2 server with host, port, and files directory."""
        self.host = host
        self.port = port
        self.files_dir = os.path.abspath(files_dir)
        
        # Validate the files directory exists
        if not os.path.exists(self.files_dir):
            print(f"Error: Directory '{self.files_dir}' not found.")
            sys.exit(1)
            
        # List available files for debugging
        print(f"Available files in {self.files_dir}:")
        for filename in os.listdir(self.files_dir):
            filepath = os.path.join(self.files_dir, filename)
            if os.path.isfile(filepath):
                print(f" - {filename} ({os.path.getsize(filepath)} bytes)")
    
    def start(self):
        """Start the HTTP/2 server and listen for connections."""
        print(f"Starting HTTP/2 server on {self.host}:{self.port}...")
        
        # Create and configure the socket
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.sock.bind((self.host, self.port))
            self.sock.listen(5)  # Allow up to 5 pending connections
            
            print(f"HTTP/2 server listening on http://{self.host}:{self.port}/")
            print("Press Ctrl+C to stop the server.")
            
            # Accept and handle connections indefinitely
            while True:
                client_socket, addr = self.sock.accept()
                print(f"Connection accepted from {addr[0]}:{addr[1]}")
                self.handle_connection(client_socket)
                
        except KeyboardInterrupt:
            print("\nServer shutdown requested.")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.sock.close()
            print("Server stopped.")
    
    def handle_connection(self, client_socket):
        """Handle an incoming HTTP/2 connection."""
        try:
            # Set up H2 connection
            config = h2.config.H2Configuration(client_side=False)
            conn = h2.connection.H2Connection(config=config)
            
            # Configure settings
            conn.local_settings = h2.settings.Settings(
                client=False,
                initial_values={
                    h2.settings.SettingCodes.MAX_CONCURRENT_STREAMS: 2**31 - 1
                }
            )
            
            # Start the connection
            conn.initiate_connection()
            client_socket.sendall(conn.data_to_send())
            
            # Process streams
            while True:
                # Try to receive data with a timeout
                client_socket.settimeout(30.0)  # 30 second timeout
                try:
                    data = client_socket.recv(65535)
                    if not data:
                        break
                except socket.timeout:
                    print("Connection timed out")
                    break
                except ConnectionResetError:
                    print("Connection reset by peer")
                    break
                
                # Process received data
                events = conn.receive_data(data)
                
                for event in events:
                    if isinstance(event, h2.events.RequestReceived):
                        self.handle_request(conn, client_socket, event)
                
                # Send any pending data
                client_socket.sendall(conn.data_to_send())
                
        except Exception as e:
            print(f"Error handling connection: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
            print("Connection closed")
    
    def handle_request(self, conn, sock, event):
        """Handle an HTTP/2 request event."""
        stream_id = event.stream_id
        
        # Extract path from headers
        request_path = None
        for header, value in event.headers:
            if header.decode() == ':path':
                request_path = value.decode()
                break
        
        if not request_path:
            self.send_error_response(conn, sock, stream_id, 400, "Bad Request: No path specified")
            return
        
        # Remove leading slash and get file path
        if request_path.startswith('/'):
            request_path = request_path[1:]
        
        file_path = os.path.join(self.files_dir, request_path)
        
        # Security check - ensure file is within files_dir
        if not os.path.normpath(file_path).startswith(os.path.normpath(self.files_dir)):
            self.send_error_response(conn, sock, stream_id, 403, "Forbidden: Access denied")
            return
        
        # Check if file exists
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error_response(conn, sock, stream_id, 404, "Not Found: File does not exist")
            return
        
        # Read and send the file
        try:
            with open(file_path, 'rb') as file:
                response_data = file.read()
            
            self.send_successful_response(conn, sock, stream_id, response_data)
            print(f"Served file: {request_path} ({len(response_data)} bytes)")
            
        except Exception as e:
            print(f"Error reading file: {e}")
            self.send_error_response(conn, sock, stream_id, 500, f"Internal Server Error: {str(e)}")
    
    def send_successful_response(self, conn, sock, stream_id, response_data):
        """Send a successful (HTTP 200) response."""
        # Send headers
        conn.send_headers(
            stream_id=stream_id,
            headers=[
                (":status", "200"),
                ("server", "http2-server/1.0"),
                ("content-length", str(len(response_data))),
                ("content-type", "application/octet-stream"),
            ],
        )
        sock.sendall(conn.data_to_send())
        
        # Send data in chunks
        chunk_size = 16384  # 16KB chunks
        for i in range(0, len(response_data), chunk_size):
            # Check flow control window
            if conn.local_flow_control_window(stream_id) < chunk_size:
                self.wait_for_window_update(sock, conn)
            
            # Send chunk
            conn.send_data(stream_id, response_data[i:i + chunk_size])
            sock.sendall(conn.data_to_send())
        
        # End the stream
        conn.end_stream(stream_id)
        sock.sendall(conn.data_to_send())
    
    def send_error_response(self, conn, sock, stream_id, status_code, error_message):
        """Send an error response."""
        error_data = error_message.encode('utf-8')
        
        conn.send_headers(
            stream_id=stream_id,
            headers=[
                (":status", str(status_code)),
                ("server", "http2-server/1.0"),
                ("content-length", str(len(error_data))),
                ("content-type", "text/plain"),
            ],
        )
        sock.sendall(conn.data_to_send())
        
        conn.send_data(stream_id, error_data)
        conn.end_stream(stream_id)
        sock.sendall(conn.data_to_send())
        
        print(f"Error response: {status_code} - {error_message}")
    
    def wait_for_window_update(self, sock, conn):
        """Wait for a flow control window update."""
        window_updated = False
        while not window_updated:
            try:
                data = sock.recv(65536)
                if not data:
                    break
                
                events = conn.receive_data(data)
                for event in events:
                    if isinstance(event, h2.events.WindowUpdated):
                        window_updated = True
                        break
                
                sock.sendall(conn.data_to_send())
                
            except Exception as e:
                print(f"Error waiting for window update: {e}")
                break

@click.command()
@click.option('--host', default='0.0.0.0', help='Host address to bind to')
@click.option('--port', default=8000, type=int, help='Port to listen on')
@click.option('--files', default='./files', help='Directory to serve files from')
@click.option('--machine', type=click.Choice(['vm1', 'vm2']), help='Predefined machine configuration')
def main(host, port, files, machine):
    """Start an HTTP/2 server to serve files."""
    if machine:
        # Load machine configuration from JSON file
        try:
            with open('machines.json', 'r') as f:
                machines = json.load(f)
            
            if machine in machines:
                host = machines[machine]
                print(f"Using configuration for {machine}: {host}")
            else:
                print(f"Warning: Machine '{machine}' not found in machines.json")
        except Exception as e:
            print(f"Error loading machines.json: {e}")
    
    # Create and start the server
    server = HTTP2Server(host, port, files)
    server.start()

if __name__ == '__main__':
    main()