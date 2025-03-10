#!/usr/bin/env python3
"""
Simple HTTP/2-compatible server for CSC/ECE 573 Project #1
Updated for Python 3.12+ compatibility
"""

import http.server
import socketserver
import ssl
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

def generate_cert_if_needed(cert_file="server.crt", key_file="server.key"):
    """Generate a self-signed certificate if it doesn't exist"""
    if os.path.exists(cert_file) and os.path.exists(key_file):
        return
    
    logger.info(f"Generating self-signed certificate...")
    
    # Use OpenSSL command-line tool to generate certificate
    cmd = f'openssl req -x509 -newkey rsa:2048 -keyout {key_file} -out {cert_file} -days 365 -nodes -subj "/CN=localhost"'
    try:
        # Try with newer OpenSSL that supports subjectAltName
        cmd_with_alt = cmd + ' -addext "subjectAltName = DNS:localhost,IP:127.0.0.1"'
        ret = os.system(cmd_with_alt)
        if ret != 0:
            # Fall back to basic command for older OpenSSL
            ret = os.system(cmd)
    except:
        # Fall back to basic command
        ret = os.system(cmd)
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        logger.info(f"Certificate generated successfully.")
    else:
        logger.error(f"Failed to generate certificate.")
        sys.exit(1)

def start_server(port=8443):
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
    
    # Generate certificate
    generate_cert_if_needed()
    
    # Create an HTTPS server with modern SSL context approach
    handler = HTTP2Handler
    
    # Create SSL context
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")
    
    # Create server
    httpd = socketserver.ThreadingTCPServer(("", port), handler)
    
    # Wrap with SSL context
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    
    logger.info(f"Serving HTTP/2 at https://0.0.0.0:{port}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    finally:
        httpd.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HTTP/2 Server for Project #1")
    parser.add_argument("--port", type=int, default=8443, help="Port to listen on (default: 8443)")
    args = parser.parse_args()
    
    start_server(args.port)