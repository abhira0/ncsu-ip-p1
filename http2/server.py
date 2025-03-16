import socket
import os
import h2.connection
import h2.config

FILE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "files")

class HTTPServer:
    def __init__(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", 8000))
        self.sock.listen(1)

    def start(self):
        print(f"Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/)")
        while True:
            self.handle(self.sock.accept()[0])

    def handle(self, sock):
        config = h2.config.H2Configuration(client_side=False)
        conn = h2.connection.H2Connection(config=config)
        conn.local_settings = h2.settings.Settings(client=False, initial_values={h2.settings.SettingCodes.MAX_CONCURRENT_STREAMS: 2**31 - 1})
        conn.initiate_connection()
        sock.sendall(conn.data_to_send())

        path =[]
        while True:
            data = sock.recv(65535)
            if not data:
                break

            events = conn.receive_data(data)
            for event in events:

                if isinstance(event, h2.events.RequestReceived):
                    for header in event.headers:
                        if header[0].decode()==':path':
                            path =header[1].decode()
                    
                    file_name = path[1:]
                    file_path = os.path.join(FILE_FOLDER, file_name)
                    with open(file_path, "rb") as file:
                        response_data = file.read()

                    self.send_successfull_response(conn,sock, event, response_data)


    def send_successfull_response(self, conn,sock, event, response_data):
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
            data = sock.recv(65536 * 1024)
            if not data:
                break
            # feed raw data into h2, and process resulting events
            events = conn.receive_data(data)
            for event in events:
                if isinstance(event, h2.events.WindowUpdated):
                    window_updated = True
        sock.sendall(conn.data_to_send())


HTTPServer().start()
