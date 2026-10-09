"""Fixed-action host administration over a Unix socket, without a Docker socket."""
import http.client
import json
import os
import socket



class UnixConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(os.environ.get('HOST_AGENT_SOCKET', '/run/mole-host-agent/control.sock'))


def request(method, path, payload=None):
    connection = UnixConnection('localhost', timeout=30)
    try:
        connection.request(method, path, json.dumps(payload) if payload is not None else None,
                           {'Content-Type': 'application/json'})
        result = connection.getresponse()
        try:
            data = json.loads(result.read())
        except ValueError as error:
            raise RuntimeError("Host agent returned invalid JSON") from error
        if result.status >= 400:
            raise RuntimeError(data.get('error', f'Host agent returned {result.status}'))
        return data
    except OSError as error:
        raise RuntimeError(f'Host agent unavailable: {error}') from error
    finally:
        connection.close()
