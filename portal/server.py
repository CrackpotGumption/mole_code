"""Same-origin cabinet portal. Run: python3 portal/server.py"""
import argparse
import json
import re
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PortalServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, *args):
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(*args)
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address
    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise
    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


ROOT = Path(__file__).parent
SPEC = json.loads((ROOT.parent / 'misc/openapi.json').read_text())


def base_url(value):
    parts = urlsplit(value)
    if parts.scheme != 'http' or not parts.hostname or parts.username or parts.password or parts.path not in ('', '/') or parts.query or parts.fragment:
        raise ValueError('Cabinet address must be an HTTP base URL, such as http://mole1.local:8080')
    _ = parts.port
    return value.rstrip('/')


def allowed(method, route):
    path = urlsplit(route).path
    if not route.startswith('/') or route.startswith('//') or '#' in route:
        return False
    return any(method.lower() in methods and re.fullmatch(re.escape(pattern).replace(r'\{id\}', r'[A-Za-z0-9_-]+'), path)
               for pattern, methods in SPEC['paths'].items())


def make_handler(addresses):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, body, content_type='application/json'):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path.startswith('/proxy/'):
                return self.proxy('GET')
            if path == '/registry':
                return self.reply(200, addresses)
            if path == '/openapi.json':
                return self.reply(200, SPEC)
            if path == '/reference':
                return self.reply(200, {'text': (ROOT.parent / 'misc/API_REFERENCE.md').read_text()})
            files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path not in files:
                return self.reply(404, {'error': 'Not found'})
            name, mime = files[path]
            self.reply(200, (ROOT / 'static' / name).read_bytes(), mime)

        def do_POST(self):
            if urlsplit(self.path).path.startswith('/proxy/'):
                return self.proxy('POST')
            self.reply(404, {'error': 'Not found'})

        def proxy(self, method):
            # Registry is fixed at server startup; callers cannot supply arbitrary destinations.
            try:
                _, _, index, tail = self.path.split('/', 3)
                cabinet = addresses[int(index)] if index in ('0', '1', '2', '3') else None
                route = '/' + tail
                if cabinet is None or not allowed(method, route):
                    return self.reply(404, {'error': 'Unknown cabinet or API route'})
                body = None
                if method == 'POST':
                    # Reject cross-origin browser control submissions.
                    origin = self.headers.get('Origin')
                    if origin and origin != 'http://' + self.headers.get('Host', ''):
                        return self.reply(403, {'error': 'Cross-origin controls are forbidden'})
                    if self.headers.get_content_type() != 'application/json':
                        return self.reply(415, {'error': 'Use application/json'})
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 4096 or self.headers.get('Transfer-Encoding'):
                        raise ValueError('JSON object must be 1–4096 bytes')
                    body = self.rfile.read(size)
                    if not isinstance(json.loads(body), dict):
                        raise ValueError('JSON body must be an object')
                request = Request(cabinet['url'] + route, data=body, method=method, headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
                try:
                    with build_opener(NoRedirect).open(request, timeout=30) as response:
                        self.reply(response.status, response.read(2_000_001), response.headers.get('Content-Type', 'application/json'))
                except HTTPError as error:
                    self.reply(error.code, error.read(2_000_001), error.headers.get('Content-Type', 'application/json'))
            except (ValueError, IndexError, KeyError) as error:
                self.reply(400, {'error': str(error)})
            except (URLError, TimeoutError, OSError) as error:
                self.reply(502, {'error': 'Cabinet unreachable: ' + str(error)})
        def log_message(self, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'cabinets.json')
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8090)
    args = parser.parse_args()
    addresses = json.loads(args.config.read_text())
    if len(addresses) != 4:
        parser.error('Configuration must contain exactly four cabinets')
    for cabinet in addresses:
        cabinet['url'] = base_url(cabinet['url'])
    server = PortalServer((args.bind, args.port), make_handler(addresses))
    server.daemon_threads = True
    print(f'Cabinet portal: http://{args.bind}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
