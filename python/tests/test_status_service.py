import http.client
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.status_service import StatusService


class SerialHTTPTests(unittest.TestCase):
    def setUp(self):
        self.arduino = Mock(running=True)
        self.arduino.send.return_value = None
        self.service = StatusService(SimpleNamespace(arduino=self.arduino), host='127.0.0.1', port=0)
        self.service.start()
        self.addCleanup(self.service.stop)

    def post(self, payload, path='/serial', content_type='application/json'):
        connection = http.client.HTTPConnection('127.0.0.1', self.service.server.server_port, timeout=2)
        self.addCleanup(connection.close)
        connection.request('POST', path, json.dumps(payload), {'Content-Type': content_type})
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_command_uses_existing_controller_queue(self):
        status, body = self.post({'command': ' RFID STATUS '})
        self.assertEqual(status, 202)
        self.assertEqual(body, {'status': 'queued', 'command': 'RFID STATUS', 'receipt': None})
        self.arduino.send.assert_called_once_with('RFID STATUS')

    def test_invalid_commands_are_not_sent(self):
        for command in ('', '  ', 'STATUS\nMOLES ALL UP', 'X' * 129, None, '\u2603'):
            with self.subTest(command=command):
                self.assertEqual(self.post({'command': command})[0], 400)
        self.assertEqual(self.post([])[0], 400)
        self.arduino.send.assert_not_called()

    def test_disconnected_returns_unavailable(self):
        self.arduino.send.side_effect = RuntimeError('Arduino connection is unavailable')
        self.assertEqual(self.post({'command': 'STATUS'})[0], 503)

    def test_unknown_path_and_wrong_content_type(self):
        self.assertEqual(self.post({'command': 'STATUS'}, path='/other')[0], 404)
        self.assertEqual(self.post({'command': 'STATUS'}, content_type='text/plain')[0], 415)
        self.arduino.send.assert_not_called()


    def test_diagnostics_endpoint(self):
        connection = http.client.HTTPConnection('127.0.0.1', self.service.server.server_port, timeout=2)
        self.addCleanup(connection.close)
        with patch('app.status_service.diagnostics', return_value={'application': {'version': '2.2.0'}}):
            connection.request('GET', '/diagnostics')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())['application']['version'], '2.2.0')
