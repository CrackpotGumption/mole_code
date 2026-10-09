import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from app.cabinet import Cabinet
from app.status_service import StatusService
from test_mole_game import Hardware


class Controller(Hardware):
    def __init__(self):
        super().__init__()
        self.running = True
        self.protocol_version = 2
        self.firmware_identity = 'FIRMWARE test 3.0.0 abc'
        self.event_handler = None
        self.event_failure = self._command_failure = None
        self.failure_reason = None
        self.lease = False
        self.mask = 31
        self.records = []
        self.health_age = 0
    def submit_command(self, command, origin='game', quiet=False):
        if command == 'LEASE ON':
            self.lease = True
        self.records.append({'id': len(self.records) + 1, 'status': 'OK', 'command': command})
        return self.records[-1]
    def get_diagnostics(self):
        return {'hardware_health': {'mcp_ready': True, 'sensor_mask': self.mask, 'rfid_ready': True, 'lease_enabled': self.lease},
                'health_age_seconds': self.health_age, 'reader_alive': True, 'writer_alive': True, 'event_worker_alive': True}
    def wait_until_idle(self, timeout=5):
        pass
    def close(self):
        self.running = False
    def command_receipts(self, identity=None):
        return self.records if identity is None else next((r for r in self.records if r['id'] == identity), None)


class CabinetTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        env = patch.dict('os.environ', {'GAME_LOG_PATH': str(self.root / 'game-events.jsonl'),
                        'FIRMWARE_HISTORY_PATH': str(self.root / 'firmware.json'),
                        'AUDIO_ENABLED': '0'})
        env.start()
        self.addCleanup(env.stop)
        self.stopped = threading.Event()
        self.controller = Controller()
        self.cabinet = Cabinet(Mock(), '/dev/test', self.stopped)
        self.addCleanup(self.cleanup)
    def cleanup(self):
        self.stopped.set()
        self.cabinet.close()
    def connect(self):
        with patch('app.cabinet.connect_verified', return_value=self.controller):
            self.cabinet._connect()
    def test_missing_hardware_is_a_visible_fault(self):
        self.controller.mask = 15
        with patch('app.cabinet.connect_verified', return_value=self.controller), self.assertRaisesRegex(RuntimeError, 'not ready'):
            self.cabinet._connect()
        self.cabinet.latch_fault('sensor missing')
        self.assertFalse(self.cabinet.health()['ready'])
        self.assertEqual(self.cabinet.get_state_dict()['controller']['fault']['message'], 'sensor missing')
        self.assertTrue((self.root / 'fault-history.json').is_file())
    def test_stale_health_and_game_errors_stop_outputs(self):
        self.connect()
        self.controller.event_failure = 'unexpected puzzle exception'
        self.cabinet.tick()
        self.assertEqual(self.cabinet.phase, 'FAULT')
        self.assertIn('SAFE STOP', [r['command'] for r in self.controller.records])
        self.assertIsNone(self.controller.event_handler)
    def test_raw_motion_requires_maintenance_and_has_receipt(self):
        self.connect()
        with self.assertRaisesRegex(ValueError, 'maintenance'):
            self.cabinet.serial('MOLE 0 UP')
        self.cabinet._act('maintenance', {})
        self.assertEqual(self.cabinet.serial('MOLE 0 UP')['status'], 'OK')
    def test_reset_game_preserves_store_and_requires_confirmation(self):
        self.connect()
        self.cabinet.game.state.completed_players.add('001')
        self.cabinet.game.log_state("TEST_STATE")
        self.cabinet._act('maintenance', {})
        with self.assertRaises(ValueError):
            self.cabinet._act('reset_game', {})
        state = self.cabinet._act('reset_game', {'confirm': 'RESET GAME'})
        self.assertEqual(state['completed_players'], [])
        self.assertTrue((self.root / 'game-events.jsonl').is_file())
        self.assertFalse(self.cabinet.game.state.ticket_dispensed)
    def test_host_power_controls_require_maintenance(self):
        with self.assertRaisesRegex(ValueError, 'maintenance'):
            self.cabinet.submit('host_reboot', {})
        self.cabinet._act('maintenance', {})
        with patch('app.cabinet.host_bridge.request', return_value={'id': 'host-job'}) as request:
            result = self.cabinet._act('host_reboot', {})
        self.assertEqual(result['id'], 'host-job')
        request.assert_called_once_with('POST', '/actions', {'action': 'reboot'})
    def test_invalid_saved_settings_does_not_prevent_status(self):
        (self.root / 'runtime-settings.json').write_text('{broken')
        cabinet = Cabinet(Mock(), '/dev/test', self.stopped)
        self.assertEqual(cabinet.get_state_dict()['controller']['phase'], 'FAULT')
    def test_faulted_cabinet_is_still_reachable_over_http(self):
        self.cabinet.latch_fault('NO SERIAL DEVICE FOUND')
        service = StatusService(self.cabinet, host='127.0.0.1', port=0)
        service.start()
        self.addCleanup(service.stop)
        connection = http.client.HTTPConnection('127.0.0.1', service.server.server_port, timeout=2)
        self.addCleanup(connection.close)
        connection.request('GET', '/health')
        response = connection.getresponse()
        self.assertEqual(response.status, 503)
        self.assertEqual(json.loads(response.read())['fault']['message'], 'NO SERIAL DEVICE FOUND')
        connection.request('GET', '/diagnostics')
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertIn('fault_history', json.loads(response.read()))
        connection.request('POST', '/maintenance', '{}', {'Content-Type': 'application/json'})
        response = connection.getresponse()
        self.assertEqual(response.status, 202)
        response.read()

    def test_admin_restore_is_explicit_and_only_applied_on_resume(self):
        self.connect()
        self.cabinet._act('maintenance', {})
        self.cabinet._act('restore_state', {'confirm': 'RESTORE GAME',
                        'state': {'completed_players': ['001'], 'active_player': '002', 'hit_progress': 1}})
        self.assertEqual(self.cabinet.game.state.status, 'MAINTENANCE')
        replacement = Controller()
        with patch('app.cabinet.connect_verified', return_value=replacement):
            self.cabinet._act('resume', {})
        self.assertEqual(self.cabinet.game.state.completed_players, {'001'})
        self.assertEqual(self.cabinet.game.state.hit_progress, 1)
        self.assertEqual(self.cabinet.game.state.status, 'PLAYING')
        self.assertIsNone(self.cabinet.pending_admin_state)

    def test_controller_reset_discards_state_and_requests_fresh_connection(self):
        self.connect()
        self.cabinet.game.state.completed_players = {'001', '002'}
        self.controller.failure_reason = 'Unexpected Arduino reset'
        self.controller.running = False
        self.cabinet.tick()
        self.assertEqual(self.cabinet.game.state.completed_players, set())
        self.assertFalse(self.cabinet.game.state.ticket_dispensed)
        self.assertEqual(self.cabinet.actions.get_nowait()[1], 'recover')

    def test_maintenance_does_not_survive_process_restart(self):
        self.cabinet._act('maintenance', {})
        fresh = Cabinet(Mock(), '/dev/test', self.stopped)
        self.assertFalse(fresh.maintenance)
