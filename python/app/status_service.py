"""Read-only observations and bounded cabinet controls."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import queue
import threading
import time
from urllib.parse import urlsplit, parse_qs

from app.diagnostics import diagnostics
from app.host_bridge import request as host_request

ROUTES = {
    'GET': ['/health', '/state', '/diagnostics', '/commands', '/commands/{id}',
            '/operations', '/operations/{id}', '/configuration', '/firmware', '/host', '/logs', '/host/jobs', '/host/configuration', '/host/packages', '/audio', '/game/events', '/api'],
    'POST': ['/serial', '/maintenance', '/resume', '/recover', '/game/badge', '/game/reset', '/game/restore',
             '/configuration', '/firmware/retry', '/host/actions', '/audio'],
}


class APIServer(ThreadingHTTPServer):
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


class StatusService:
    def __init__(self, game, host='0.0.0.0', port=8080):
        self.game, self.host, self.port = game, host, port
        self.started_at = time.monotonic()
        service = self
        runtime = callable(getattr(type(game), 'health', None))

        class Handler(BaseHTTPRequestHandler):
            def json_response(self, status, payload):
                body = json.dumps(payload).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def payload(self):
                if self.headers.get_content_type() != 'application/json':
                    self.json_response(415, {'error': 'Use Content-Type: application/json'})
                    return None
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 4096 or self.headers.get('Transfer-Encoding'):
                        raise ValueError('Provide a JSON body of at most 4096 bytes')
                    self.connection.settimeout(5)
                    result = json.loads(self.rfile.read(size))
                    if not isinstance(result, dict):
                        raise ValueError('JSON body must be an object')
                    return result
                except (ValueError, OSError) as error:
                    self.json_response(400, {'error': str(error)})
                    return None

            def do_POST(self):
                path = urlsplit(self.path).path
                if path not in ROUTES['POST']:
                    self.json_response(404, {'error': 'Not found'})
                    return
                payload = self.payload()
                if payload is None:
                    return
                try:
                    if path == '/serial':
                        target = payload.get('target', 'arduino')
                        if target in ('host', 'game') and runtime:
                            action = str(payload.get('command', '')).lower().replace(' ', '_')
                            if target == 'host':
                                action = 'host_' + action
                            self.json_response(202, service.game.submit(action, payload))
                            return
                        if target != 'arduino':
                            raise ValueError('target must be arduino, host, or game')
                        command = payload.get('command')
                        if (not isinstance(command, str) or not command.strip() or len(command) > 128
                                or any(ord(c) < 32 or ord(c) > 126 for c in command)):
                            raise ValueError('command must be one printable ASCII line, 1–128 characters')
                        if runtime:
                            receipt = service.game.serial(command.strip())
                        else:
                            receipt = service.game.arduino.send(command.strip())
                        self.json_response(202, {'status': 'queued', 'command': command.strip(), 'receipt': receipt})
                        return
                    if not runtime:
                        raise RuntimeError('Cabinet controls are unavailable')
                    action = {'/maintenance': 'maintenance', '/resume': 'resume', '/recover': 'recover',
                              '/game/badge': 'badge', '/game/reset': 'reset_game', '/game/restore': 'restore_state',
                              '/configuration': 'configure', '/firmware/retry': 'firmware_retry', '/audio': 'audio'}.get(path)
                    if path == '/host/actions':
                        action = 'host_' + str(payload.get('action', ''))
                    self.json_response(202, service.game.submit(action, payload))
                except queue.Full:
                    self.json_response(429, {'error': 'Operation queue is full'})
                except ValueError as error:
                    self.json_response(400, {'error': str(error)})
                except RuntimeError as error:
                    self.json_response(503, {'error': str(error)})

            def do_GET(self):
                path = urlsplit(self.path).path
                try:
                    if path == '/api':
                        self.json_response(200, {'version': 1, 'routes': ROUTES, 'controls_authentication': 'none; router/LAN access',
                                                'host_actions': ['update', 'restart_game', 'update_installation', 'os_update', 'hostname', 'configuration', 'reboot', 'poweroff'],
                                                'control_examples': {
                                                    'maintenance': {}, 'resume': {}, 'recover': {},
                                                    'serial': {'target': 'arduino', 'command': 'RFID STATUS'},
                                                    'badge': {'player': '001'}, 'reset': {'confirm': 'RESET GAME'},
                                                    'restore': {'state': {'completed_players': ['001'], 'active_player': None, 'hit_progress': 0}, 'confirm': 'RESTORE GAME'},
                                                    'firmware_retry': {'confirm': 'FLASH MEGA'},
                                                    'os_update': {'action': 'os_update', 'confirm': 'UPDATE OS'},
                                                    'configuration': {'settings': {'FAILURE_SECONDS': 15, 'VICTORY_SECONDS': 19, 'IDLE_FRAME_SECONDS': 2}}},
                                                'notes': ['Queued is not executed; inspect receipts/operations',
                                                          'Raw hardware changes and host actions require maintenance',
                                                          'Host details require the host agent']})
                    elif path == '/health':
                        report = service.game.health() if runtime else {'status': 'ok' if service.game.arduino.running else 'disconnected', 'ready': service.game.arduino.running}
                        self.json_response(200 if report['ready'] else 503, report)
                    elif path == '/state':
                        self.json_response(200, service.game.get_state_dict())
                    elif path == '/diagnostics':
                        self.json_response(200, service.game.get_diagnostics() if runtime else diagnostics(service.game, service.started_at))
                    elif path in ('/host', '/logs', '/host/jobs', '/host/configuration', '/host/packages'):
                        self.json_response(200, host_request('GET', {'/host/jobs': '/jobs', '/host/configuration': '/configuration', '/host/packages': '/packages'}.get(path, path) + ('?' + urlsplit(self.path).query if path == '/logs' and urlsplit(self.path).query else '')))
                    elif path == '/game/events' and runtime:
                        limit = int(parse_qs(urlsplit(self.path).query).get('limit', ['100'])[0])
                        from app.state_log import StateLog
                        events = (service.game.game.state_log if service.game.game else StateLog(service.game.state_directory / 'game-events.jsonl'))
                        self.json_response(200, events.events(limit))
                    elif path == '/audio' and runtime:
                        self.json_response(200, service.game.audio.get_diagnostics() if service.game.audio else {'enabled': False})
                    elif path == '/configuration' and runtime:
                        self.json_response(200, service.game.configuration())
                    elif path == '/firmware' and runtime:
                        self.json_response(200, service.game.get_diagnostics()['firmware_history'])
                    elif path.startswith('/commands'):
                        controller = service.game.arduino
                        if not controller:
                            self.json_response(503, {'error': 'No connected controller'})
                            return
                        session = parse_qs(urlsplit(self.path).query).get('session', [None])[0]
                        if session is not None and session != controller.session_id:
                            self.json_response(404, {'error': 'Controller session has changed'})
                            return
                        identity = int(path.rsplit('/', 1)[1]) if path != '/commands' else None
                        result = controller.command_receipts(identity)
                        self.json_response(404 if result is None else 200, result or [])
                    elif path.startswith('/operations') and runtime:
                        with service.game.lock:
                            result = (list(service.game.operations.values()) if path == '/operations'
                                      else service.game.operations.get(path.rsplit('/', 1)[1]))
                        self.json_response(404 if result is None else 200, result or [])
                    else:
                        self.json_response(404, {'error': 'Not found'})
                except ValueError as error:
                    self.json_response(400, {'error': str(error)})
                except (RuntimeError, OSError) as error:
                    self.json_response(503, {'error': str(error)})

            def log_message(self, *args):
                pass

        self.server = APIServer((host, port), Handler)

    def start(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        print(f'API service running on port {self.server.server_port}')

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
