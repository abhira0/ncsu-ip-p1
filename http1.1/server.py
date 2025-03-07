import http.server
import socketserver
import os
import argparse
import sys

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.files_dir = os.path.abspath("./files")
        super().__init__(*args, directory=self.files_dir, **kwargs)
    
    def end_headers(self):
        self.send_header('Connection', 'close')  # make sure connection closes after each request
        super().end_headers()

def start_server(port=8000):
    files_dir = os.path.abspath("./files")
    if not os.path.exists(files_dir):
        print(f"Error: Directory './files' not found. Please create it and add your test files.")
        sys.exit(1)
        
    print(f"Available files in {files_dir}:")
    for filename in os.listdir(files_dir):
        print(f" - {filename} ({os.path.getsize(os.path.join(files_dir, filename))} bytes)")
    
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), CustomHTTPRequestHandler) as httpd:
        print(f"Serving HTTP on 0.0.0.0 port {port} (http://0.0.0.0:{port}/)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
            print("Server stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='HTTP/1.1 Server for Protocol Testing')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on (default: 8000)')
    args = parser.parse_args()
    
    start_server(args.port)