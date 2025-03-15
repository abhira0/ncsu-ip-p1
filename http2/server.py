from hypercorn.config import Config
from hypercorn.asyncio import serve
from quart import Quart, send_file
import os
import sys
import json
import click
import h2.connection
import h2.config

SERVER_ADDRESS = "0.0.0.0", 8000
FILE_FOLDER = "./files/"

class HTTPServer:
    def __init__(self):
        """Inits the socket, start listening on 8080"""
        print("server starting..")
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(SERVER_ADDRESS)
        self.sock.listen(1)

    def start(self):
        """Start listening to connections"""
        print("server listening for connections..")
        while True:
            self.handle(self.sock.accept()[0])

    def handle(self, sock):
        config = h2.config.H2Configuration(client_side=False)
        conn = h2.connection.H2Connection(config=config)
        conn.local_settings = h2.settings.Settings(client=False, initial_values={h2.settings.SettingCodes.MAX_CONCURRENT_STREAMS: 2**31 - 1})
        conn.initiate_connection()
        sock.sendall(conn.data_to_send())

        headers = {}
        path =[]
        while True:
            data = sock.recv(65535)
            if not data:
                break

            events = conn.receive_data(data)
            for event in events:

                # Recieve and process headers
                if isinstance(event, h2.events.RequestReceived):
                    for header in event.headers:
                        if header[0].decode()==':path':
                            path =header[1].decode()
                    
                    #print("Received request for ", headers["path"])

                    # path is /file_name extract file_name
                    file_name = path[1:]
                    # read the file and send it
                    file_path = FILE_FOLDER + file_name
                    with open(file_path, "rb") as file:
                        response_data = file.read()

                    self.send_successfull_response(conn,sock, event, response_data)
                    #print("Sent response for ", headers["path"])


    def send_successfull_response(self, conn,sock, event, response_data):
        """Send a successfull (HTTP 200) response"""

        stream_id = event.stream_id
        conn.send_headers(
            stream_id=stream_id,
            headers=[
                (":status", "200"),
                ("server", "basic-h2-server/1.0"),
                ("content-length", str(len(response_data))),
                ("content-type", "text/html"),
            ],
        )
        sock.sendall(conn.data_to_send())
        for i in range(0, len(response_data), 16384):
            if conn.local_flow_control_window(stream_id) < 16384:
                self.wait_for_window_update(sock, conn)
            conn.send_data(stream_id, response_data[i : i + 16384])
            sock.sendall(conn.data_to_send())
        conn.end_stream(stream_id)
        sock.sendall(conn.data_to_send())

    def wait_for_window_update(self, sock, conn):
        window_updated = False
        while not window_updated:
            # read raw data from the self.socket
            data = sock.recv(65536 * 1024)
            if not data:
                break

            # feed raw data into h2, and process resulting events
            events = conn.receive_data(data)
            for event in events:
                if isinstance(event, h2.events.WindowUpdated):
                    window_updated = True
        sock.sendall(conn.data_to_send())


if __name__ == "__main__":
    server = HTTPServer()
    server.start()