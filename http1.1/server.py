import http.server
import socketserver
import os

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "files")
        self.files_dir = os.path.abspath(file_path)
        super().__init__(*args, directory=self.files_dir, **kwargs)
    
    def end_headers(self):
        self.send_header('Connection', 'close')  # make sure connection closes after each request
        super().end_headers()

def start_server(port=8000):
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

start_server()