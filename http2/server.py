from hypercorn.config import Config
from hypercorn.asyncio import serve
from quart import Quart, send_file
import os
import sys
import asyncio
import click

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
@click.option('--port', default=8000, help='Port to run the server on')
def main(port):
    files_dir = os.path.abspath("./files")
    if not os.path.exists(files_dir):
        print(f"Error: Directory './files' not found. Please create it and add your test files.")
        sys.exit(1)
    
    print(f"Available files in {files_dir}:")
    for filename in os.listdir(files_dir):
        print(f" - {filename} ({os.path.getsize(os.path.join(files_dir, filename))} bytes)")
    
    config = Config()
    config.bind = [f"0.0.0.0:{port}"]
    
    # Configure for HTTP/2 over cleartext
    config.h2_protocol = True
    config.use_reloader = True
    
    print(f"Starting HTTP/2 server on http://0.0.0.0:{port}")
    asyncio.run(serve(app, config))

if __name__ == "__main__":
    main()