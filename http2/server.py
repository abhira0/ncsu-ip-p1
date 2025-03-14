import os
import sys
from quart import Quart, send_from_directory
import click
import asyncio

app = Quart(__name__)

@app.route('/<path:filename>')
async def serve_file(filename):
    files_dir = os.path.abspath("./files")
    return await send_from_directory(files_dir, filename)

@click.command()
@click.option('--port', default=8001, help='Port to run the server on')
def start_server(port):
    files_dir = os.path.abspath("./files")
    if not os.path.exists(files_dir):
        print(f"Error: Directory './files' not found. Please create it and add your test files.")
        sys.exit(1)
        
    print(f"Available files in {files_dir}:")
    for filename in os.listdir(files_dir):
        file_path = os.path.join(files_dir, filename)
        print(f" - {filename} ({os.path.getsize(file_path)} bytes)")
    
    print(f"Starting HTTP/2 server on port {port}...")
    app.run(host='0.0.0.0', port=port, certfile='cert.pem', keyfile='key.pem')

if __name__ == "__main__":
    start_server()