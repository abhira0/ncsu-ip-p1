import http.server
import socketserver
import logging
import os
import argparse
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='http_server.log'
)

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Use the files directory specified
        self.files_dir = os.path.abspath("./files")
        super().__init__(*args, directory=self.files_dir, **kwargs)
    
    def log_message(self, format, *args):
        logging.info(f"{self.client_address[0]} - {format%args}")
        
    def end_headers(self):
        self.send_header('Connection', 'close')  # Ensure connection closes after each request
        super().end_headers()

def start_server(port=8000):
    # Ensure the files directory exists
    files_dir = os.path.abspath("./files")
    if not os.path.exists(files_dir):
        print(f"Error: Directory './files' not found. Please create it and add your test files.")
        logging.error(f"Directory './files' not found")
        sys.exit(1)
        
    # List available files
    print(f"Available files in {files_dir}:")
    for filename in os.listdir(files_dir):
        print(f" - {filename} ({os.path.getsize(os.path.join(files_dir, filename))} bytes)")
    
    # Only allow one connection at a time
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), CustomHTTPRequestHandler) as httpd:
        print(f"Serving HTTP on 0.0.0.0 port {port} (http://0.0.0.0:{port}/)")
        logging.info(f"Server started on port {port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
            print("Server stopped.")
            logging.info("Server stopped")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='HTTP/1.1 Server for Protocol Testing')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on (default: 8000)')
    args = parser.parse_args()
    
    start_server(args.port)