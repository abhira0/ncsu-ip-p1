from quart import Quart, send_file
import os
import sys
import ssl
import click
import asyncio
import hypercorn.asyncio
from hypercorn.config import Config

app = Quart(__name__)

@app.route('/<filename>')
async def serve_file(filename):
    """Serve requested file from the files directory"""
    files_dir = os.path.abspath("./files")
    file_path = os.path.join(files_dir, filename)
    
    if not os.path.exists(file_path):
        return {"error": f"File {filename} not found"}, 404
    
    return await send_file(file_path)

@click.command()
@click.option('--port', default=8443, help='Port to run the server on')
@click.option('--with-tls/--without-tls', default=True, 
              help='Enable/disable TLS (HTTP/2 requires TLS in browsers, but not for direct connections)')
def start_server(port, with_tls):
    files_dir = os.path.abspath("./files")
    if not os.path.exists(files_dir):
        print(f"Error: Directory './files' not found. Please create it and add your test files.")
        sys.exit(1)
    
    print(f"Available files in {files_dir}:")
    for filename in os.listdir(files_dir):
        print(f" - {filename} ({os.path.getsize(os.path.join(files_dir, filename))} bytes)")
    
    config = Config()
    config.bind = [f"0.0.0.0:{port}"]
    config.alpn_protocols = ["h2", "http/1.1"] if with_tls else ["h2c", "http/1.1"]
    
    if with_tls:
        # Check for certificates
        cert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cert.pem")
        key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "key.pem")
        
        if not (os.path.exists(cert_path) and os.path.exists(key_path)):
            print("Certificates not found. Creating self-signed certificates...")
            os.system(f"openssl req -x509 -newkey rsa:4096 -nodes -out {cert_path} "
                     f"-keyout {key_path} -days 365 -subj '/CN=localhost'")
        
        config.certfile = cert_path
        config.keyfile = key_path
        
        print(f"Serving HTTP/2 with TLS on 0.0.0.0 port {port} (https://0.0.0.0:{port}/)")
    else:
        print(f"Serving HTTP/2 without TLS on 0.0.0.0 port {port} (http://0.0.0.0:{port}/)")
        # Explicitly set h2c for cleartext HTTP/2
        config.h2_protocol = "h2c"
    
    asyncio.run(hypercorn.asyncio.serve(app, config))

if __name__ == "__main__":
    start_server()