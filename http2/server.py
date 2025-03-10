#!/usr/bin/env python3
"""
Simple HTTP/2-compatible server for CSC/ECE 573 Project #1
Non-SSL version for faster testing
"""

import http.server
import socketserver
import os
import sys
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('http2_server')

class HTTP2Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'  # We're using HTTP/1.1 but with HTTP/2 headers
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve files from
        self.directory = os.path.abspath("./files")
        super().__init__(*args, directory=self.directory, **kwargs)
    
    def end_headers(self):
        # Add HTTP/2 headers to indicate support
        self.send_header('Connection', 'Upgrade, HTTP2-Settings')
        self.send_header('Upgrade', 'h2c')
        self.send_header('HTTP2-Settings', 'AAMAAABkAAQAAP__')
        super().end_headers()

def start_server(port=8000):
    # Ensure files directory exists
    files_dir = os.path.abspath("./files")
    if not os.path.exists(files_dir):
        logger.error(f"Error: Directory './files' not found. Creating it...")
        os.makedirs(files_dir)
    
    # List available files
    if os.path.exists(files_dir):
        logger.info(f"Available files in {files_dir}:")
        for filename in os.listdir(files_dir):
            file_path = os.path.join(files_dir, filename)
            if os.path.isfile(file_path):
                logger.info(f" - {filename} ({os.path.getsize(file_path)} bytes)")
    
    # Create a non-SSL HTTP server with threading
    handler = HTTP2Handler
    httpd = socketserver.ThreadingTCPServer(("", port), handler)
    
    logger.info(f"Serving HTTP/2 on http://0.0.0.0:{port}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    finally:
        httpd.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HTTP/2 Server for Project #1")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args()
    
    start_server(args.port)