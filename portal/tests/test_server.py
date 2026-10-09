import importlib.util
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('portal_server', Path(__file__).parents[1] / 'server.py')
portal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portal)

class ProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Cabinet(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(503 if self.path == '/health' else 200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'ready': False, 'phase': 'MAINTENANCE', 'path': self.path}).encode())
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                self.send_response(202)
                self.end_headers()
                self.wfile.write(json.dumps({'id': 'test-operation', 'payload': body}).encode())
            def log_message(self, *args): pass
        cls.cabinet = ThreadingHTTPServer(('127.0.0.1', 0), Cabinet)
        entries = [{'name': str(i), 'url': f'http://127.0.0.1:{cls.cabinet.server_port}'} for i in range(4)]
        cls.server = portal.PortalServer(('127.0.0.1', 0), portal.make_handler(entries))
        for server in [cls.cabinet, cls.server]:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        for server in [cls.server, cls.cabinet]:
            server.shutdown()
            server.server_close()
    def call(self, path, body=None, **headers):
        req = Request(self.url + path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json', **headers})
        try: response = urlopen(req)
        except HTTPError as error: response = error
        with response:
            return response.status, json.loads(response.read())
    def test_health_503_preserves_body(self):
        status, body = self.call('/proxy/0/health')
        self.assertEqual(status, 503)
        self.assertFalse(body['ready'])
    def test_serial_post(self):
        status, body = self.call('/proxy/3/serial', {'command': 'PING'})
        self.assertEqual(status, 202)
        self.assertEqual(body['payload'], {'command': 'PING'})
    def test_session_query_preserved(self):
        _, body = self.call('/proxy/1/commands/42?session=abc')
        self.assertEqual(body['path'], '/commands/42?session=abc')
    def test_routes_and_targets_restricted(self):
        for path in ['/proxy/4/health', '/proxy/0/unknown', '/proxy/0//evil.test/health']:
            self.assertEqual(self.call(path)[0], 404)
    def test_cross_origin_control_rejected(self):
        self.assertEqual(self.call('/proxy/0/maintenance', {}, Origin='http://evil.test')[0], 403)
    def test_object_body_required(self):
        self.assertEqual(self.call('/proxy/0/maintenance', [1])[0], 400)
    def test_url_validation(self):
        for value in ['https://mole1.local', 'http://user:pass@mole1.local', 'http://mole1.local/path']:
            with self.assertRaises(ValueError): portal.base_url(value)
        self.assertEqual(portal.base_url('http://mole1.local:8080/'), 'http://mole1.local:8080')

if __name__ == '__main__': unittest.main()
