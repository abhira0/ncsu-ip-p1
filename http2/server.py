from hypercorn.config import Config
from hypercorn.asyncio import serve
from quart import Quart, send_file
import os
import asyncio

app = Quart(__name__)

@app.route('/<filename>')
async def serve_file(filename):
    files_dir = os.path.abspath("./files")
    file_path = os.path.join(files_dir, filename)
    
    if not os.path.exists(file_path):
        return {"error": f"File {filename} not found"}, 404
    
    return await send_file(file_path)

def main():
    config = Config()
    config.bind = [f"0.0.0.0:8000"]
    config.h2_protocol = True
    config.use_reloader = True
    
    print(f"Starting HTTP/2 server on http://0.0.0.0:8000")
    asyncio.run(serve(app, config))

main()