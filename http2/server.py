import os
import sys
import argparse
import ssl
import json
from pathlib import Path
from http.server import HTTPServer
from aiohttp import web
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HTTP2Server:
    def __init__(self, host='0.0.0.0', port=8443, cert_file='server.crt', key_file='server.key'):
        self.host = host
        self.port = port
        self.cert_file = cert_file
        self.key_file = key_file
        self.files_dir = Path('./files').absolute()
        
        if not self.files_dir.exists():
            logger.error(f"Error: Directory '{self.files_dir}' not found. Please create it and add your test files.")
            sys.exit(1)
        
        # Display available files
        logger.info(f"Available files in {self.files_dir}:")
        for file_path in self.files_dir.iterdir():
            if file_path.is_file():
                logger.info(f" - {file_path.name} ({file_path.stat().st_size} bytes)")
    
    async def handle_request(self, request):
        """Handle HTTP requests and serve files"""
        path = request.path.strip('/')
        file_path = self.files_dir / path
        
        if not file_path.exists() or not file_path.is_file():
            return web.Response(text="File not found", status=404)
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            return web.Response(
                body=content,
                headers={
                    'Content-Type': 'application/octet-stream',
                    'Content-Length': str(len(content))
                }
            )
        except Exception as e:
            logger.error(f"Error serving file: {e}")
            return web.Response(text=str(e), status=500)
    
    def generate_self_signed_cert(self):
        """Generate a self-signed certificate if it doesn't exist"""
        if os.path.exists(self.cert_file) and os.path.exists(self.key_file):
            logger.info(f"Using existing certificate ({self.cert_file}) and key ({self.key_file}).")
            return
        
        logger.info(f"Generating self-signed certificate ({self.cert_file}) and key ({self.key_file})...")
        
        # Use openssl command to generate self-signed certificate
        os.system(f'openssl req -x509 -newkey rsa:2048 -keyout {self.key_file} -out {self.cert_file} '
                  f'-days 365 -nodes -subj "/C=US/ST=NC/L=Raleigh/O=NCSU/OU=CSC/CN=localhost"')
        
        logger.info("Certificate generated successfully.")
    
    async def start(self):
        """Start the HTTP/2 server"""
        # Generate certificate if needed
        self.generate_self_signed_cert()
        
        # Create SSL context
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(self.cert_file, self.key_file)
        
        # Setup HTTP/2 support
        ssl_context.set_alpn_protocols(['h2', 'http/1.1'])
        
        # Create app and routes
        app = web.Application()
        app.router.add_get('/{tail:.*}', self.handle_request)
        
        # Start server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port, ssl_context=ssl_context)
        
        logger.info(f"Starting HTTP/2 server on {self.host}:{self.port}")
        await site.start()
        
        logger.info(f"Server running at https://{self.host}:{self.port}")
        logger.info("Press Ctrl+C to stop the server")
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
            
def main():
    parser = argparse.ArgumentParser(description='HTTP/2 Server for Protocol Testing')
    parser.add_argument('--port', type=int, default=8443, help='Port to run the server on (default: 8443)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind the server to (default: 0.0.0.0)')
    args = parser.parse_args()
    
    server = HTTP2Server(host=args.host, port=args.port)
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped.")

if __name__ == "__main__":
    main()