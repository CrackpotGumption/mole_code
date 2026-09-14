import json
import threading

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)


class StatusService:

    def __init__(
        self,
        game,
        host="0.0.0.0",
        port=8080,
    ):
        self.game = game
        self.host = host
        self.port = port

        service = self

        class Handler(BaseHTTPRequestHandler):

            def do_GET(self):

                if self.path == "/state":

                    state = (
                        service.game.get_state_dict()
                    )

                    body = json.dumps(
                        state,
                        indent=2,
                    ).encode("utf-8")

                    self.send_response(200)

                    self.send_header(
                        "Content-Type",
                        "application/json",
                    )

                    self.send_header(
                        "Content-Length",
                        str(len(body)),
                    )

                    self.end_headers()

                    self.wfile.write(body)

                    return


                if self.path == "/health":

                    body = b'{"status":"ok"}'

                    self.send_response(200)

                    self.send_header(
                        "Content-Type",
                        "application/json",
                    )

                    self.send_header(
                        "Content-Length",
                        str(len(body)),
                    )

                    self.end_headers()

                    self.wfile.write(body)

                    return


                self.send_response(404)
                self.end_headers()


            def log_message(
                self,
                format,
                *args,
            ):
                # Suppress normal HTTP request logging.
                return


        self.server = ThreadingHTTPServer(
            (
                self.host,
                self.port,
            ),
            Handler,
        )


    def start(self):

        thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )

        thread.start()

        print(
            f"Status service running "
            f"on port {self.port}"
        )