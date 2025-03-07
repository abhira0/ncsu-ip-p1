import socketserver
import ssl
import json
import argparse
import os
import sys
from http.server import BaseHTTPRequestHandler
from hyper import HTTP20Connection
from twisted.web import server, resource
from twisted.internet import ssl, reactor, endpoints
from twisted.python import log
from OpenSSL import crypto

def generate_self_signed_cert(cert_file="server.crt", key_file="server.key"):
    # Generate a self-signed certificate if it doesn't exist
    if not (os.path.exists(cert_file) and os.path.exists(key_file)):
        print(f"Generating self-signed certificate ({cert_file}) and key ({key_file})...")
        
        # Create a key pair
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)
        
        # Create a self-signed cert
        cert = crypto.X509()
        cert.get_subject().C = "US"
        cert.get_subject().ST = "NC"
        cert.get_subject().L = "Raleigh"
        cert.get_subject().O = "NCSU"
        cert.get_subject().OU = "CSC/ECE 573"
        cert.get_subject().CN = "localhost"
        cert.set_serial_number(1000)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10*365*24*60*60)  # 10 years
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, 'sha256')
        
        # Save the certificate and key files
        with open(cert_file, "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        
        with open(key_file, "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
            
        print("Certificate generated successfully.")
    else:
        print(f"Using existing certificate ({cert_file}) and key ({key_file}).")

class FileResource(resource.Resource):
    isLeaf = True
    
    def __init__(self, files_dir):
        self.files_dir = files_dir
        resource.Resource.__init__(self)
        
    def render_GET(self, request):
        path = request.path.decode('utf-8').strip('/')
        file_path = os.path.join(self.files_dir, path)
        
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            request.setResponseCode(404)
            return b"File not found"
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                
            request.setHeader(b"Content-Length", str(len(content)).encode())
            request.setHeader(b"Content-Type", b"application/octet-stream")
            return content
        except Exception as e:
            request.setResponseCode(500)
            return str(e).encode()

def start_server(port=8443):
    # Setup file directory
    files_dir = os.path.abspath("./files")
    if not os.path.exists(files_dir):
        print(f"Error: Directory './files' not found. Please create it and add your test files.")
        sys.exit(1)
        
    print(f"Available files in {files_dir}:")
    for filename in os.listdir(files_dir):
        print(f" - {filename} ({os.path.getsize(os.path.join(files_dir, filename))} bytes)")
    
    # Generate certificate if needed
    generate_self_signed_cert()
    
    # Setup Twisted with TLS
    root = FileResource(files_dir)
    site = server.Site(root)
    
    ssl_context = ssl.DefaultOpenSSLContextFactory(
        'server.key', 'server.crt'
    )
    
    # Setup HTTP/2 server with TLS
    endpoint = endpoints.SSL4ServerEndpoint(reactor, port, ssl_context)
    endpoint.listen(site)
    
    print(f"Serving HTTP/2 on 0.0.0.0 port {port} (https://0.0.0.0:{port}/)")
    print("Press Ctrl+C to stop the server")
    
    try:
        reactor.run()
    except KeyboardInterrupt:
        pass
    finally:
        if reactor.running:
            reactor.stop()
        print("Server stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='HTTP/2 Server for Protocol Testing')
    parser.add_argument('--port', type=int, default=8443, help='Port to run the server on (default: 8443)')
    args = parser.parse_args()
    
    # Enable logging
    log.startLogging(sys.stdout)
    
    start_server(args.port)