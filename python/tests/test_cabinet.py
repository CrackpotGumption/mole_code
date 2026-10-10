import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from app.cabinet import Cabinet, hardware_guidance
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
        waiting = patch.object(self.stopped, 'wait', return_value=False)
        waiting.start()
        self.addCleanup(waiting.stop)
    def test_hardware_messages_identify_sensor_and_where_to_check(self):
        report = {'mcp_ready': True, 'sensor_mask': 29, 'rfid_ready': True, 'lease_enabled': False}
        message = hardware_guidance(report, require_lease=True)
        self.assertIn('Sensor 1 (DAPHNE, front center, mux channel 1)', message)
        self.assertIn('SDA/SCL', message)
        self.assertNotIn('keepalive', message)
        self.assertNotIn('sensor_mask', message)
        report['sensor_mask'] = 26
        message = hardware_guidance(report)
        self.assertIn('Sensor 0 (MARTIN, front left', message)
        self.assertIn('Sensor 2 (NILES, front right', message)
        self.assertNotIn('Sensor 1', message)
        report['sensor_mask'] = 31
        self.assertIn('keepalive', hardware_guidance(report, require_lease=True))
        self.assertIn('USB', hardware_guidance(None))

    def test_startup_missing_sensor_warns_and_preserves_raw_diagnostics(self):
        self.controller.mask = 29
        self.connect()
        health = self.cabinet.health()
        self.assertTrue(health['ready'])
        self.assertEqual(health['phase'], 'WARN')
        self.assertIn('Sensor 1 (DAPHNE, front center, mux channel 1)', health['warning']['message'])
        self.assertEqual(self.cabinet._last_probe_report['sensor_mask'], 29)
        self.assertIsNone(self.cabinet.fault)

    def test_victory_duration_is_owned_by_app_settings(self):
        with patch.dict('os.environ', {'VICTORY_SECONDS': '90'}):
            upgraded = Cabinet(Mock(), '/dev/test', self.stopped)
            self.assertEqual(upgraded.configuration()['VICTORY_SECONDS'], '19')
            (self.root / 'runtime-settings.json').write_text(json.dumps({'VICTORY_SECONDS': 37}))
            configured = Cabinet(Mock(), '/dev/test', self.stopped)
            self.assertEqual(configured.configuration()['VICTORY_SECONDS'], '37')
            self.assertEqual(json.loads((self.root / 'runtime-settings.json').read_text())['VICTORY_SECONDS'], 37)

    def test_fifo_configuration_and_serial_modes_are_disabled(self):
        for key, value in {'HIT_THRESHOLD_COUNTS': 4500, 'HIT_ARM_DELAY_MS': 1500,
                           'HIT_AXIS': 'Y', 'HIT_DEBUG': 1}.items():
            with self.assertRaisesRegex(ValueError, 'FIFO tuning is disabled'):
                self.cabinet.submit('configure', {'settings': {key: value}})
            with self.assertRaisesRegex(ValueError, 'FIFO tuning is disabled'):
                self.cabinet._act('configure', {'settings': {key: value}})
            self.assertNotIn(key, self.cabinet.configuration())
        self.cabinet.arduino = self.controller
        self.cabinet.maintenance = True
        for command in ('SENSORS FIFO 4500 1500 Y', 'SENSORS PUZZLE', 'HIT_DEBUG ON'):
            with self.assertRaisesRegex(ValueError, 'disabled in V3'):
                self.cabinet.serial(command)

    def test_saved_fifo_settings_are_retired_without_startup_fault(self):
        saved = {'HIT_THRESHOLD_COUNTS': 4500, 'HIT_ARM_DELAY_MS': 1500,
                 'HIT_AXIS': 'Y', 'HIT_DEBUG': 1, 'FAILURE_SECONDS': 5}
        (self.root / 'runtime-settings.json').write_text(json.dumps(saved))
        upgraded = Cabinet(Mock(), '/dev/test', self.stopped)
        self.assertIsNone(upgraded.fault)
        self.assertEqual(upgraded.settings, {'FAILURE_SECONDS': 5})
        self.assertEqual(json.loads((self.root / 'runtime-settings.json').read_text()), {'FAILURE_SECONDS': 5})

    def test_startup_recovery_backoff_and_never_restarts_active_game(self):
        self.cabinet._startup_retry_eligible = True
        self.cabinet.latch_fault('serial transport unavailable')
        with patch('app.cabinet.time.monotonic', return_value=100):
            self.cabinet._schedule_startup_retry()
        self.assertEqual(self.cabinet._startup_retry_at, 130)
        self.cabinet._retry_startup(129)
        self.assertTrue(self.cabinet.actions.empty())
        self.cabinet._retry_startup(130)
        self.assertEqual(self.cabinet._startup_retry_attempts, 1)
        self.assertEqual(self.cabinet.actions.qsize(), 1)
        self.cabinet._retry_startup(131)
        self.assertEqual(self.cabinet.actions.qsize(), 1)
        _, action, _ = self.cabinet.actions.get_nowait()
        self.cabinet.actions.task_done()
        self.assertEqual(action, 'recover')
        self.cabinet._startup_retry_queued = False
        with patch('app.cabinet.time.monotonic', return_value=200):
            self.cabinet._schedule_startup_retry()
        self.assertEqual(self.cabinet._startup_retry_at, 260)
        self.cabinet.maintenance = True
        self.cabinet._retry_startup(300)
        self.assertTrue(self.cabinet.actions.empty())
        self.cabinet.maintenance = False
        self.cabinet.game = Mock()
        self.cabinet._retry_startup(300)
        self.assertTrue(self.cabinet.actions.empty())
        self.cabinet.game = None
        self.cabinet._startup_retry_attempts = 3
        self.cabinet._schedule_startup_retry()
        self.assertIsNone(self.cabinet._startup_retry_at)

    def cleanup(self):
        self.stopped.set()
        self.cabinet.close()
    def connect(self):
        with patch('app.cabinet.connect_verified', return_value=self.controller):
            self.cabinet._connect()
    def test_missing_hardware_is_a_visible_warning(self):
        self.controller.mask = 15
        self.connect()
        self.assertTrue(self.cabinet.health()['ready'])
        self.assertIn('Sensor 4 (ROZ, back right', self.cabinet.health()['warning']['message'])
        self.assertIsNone(self.cabinet.fault)

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

    def test_ready_uses_health_snapshot_taken_after_lease_enabled(self):
        class SnapshotController(Controller):
            reported_lease = False
            def submit_command(self, command, **kwargs):
                result = super().submit_command(command, **kwargs)
                if command == 'HEALTH':
                    self.reported_lease = self.lease
                return result
            def get_diagnostics(self):
                report = super().get_diagnostics()
                report['hardware_health']['lease_enabled'] = self.reported_lease
                return report
        self.controller = SnapshotController()
        self.connect()
        self.cabinet.tick()
        self.assertTrue(self.cabinet.health()['ready'])
        self.assertIsNone(self.cabinet.fault)
        commands = [r['command'] for r in self.controller.records]
        lease_index = commands.index('LEASE ON')
        self.assertEqual(commands[lease_index + 1], 'HEALTH')

    def test_audio_volume_is_persisted_applied_live_and_validated(self):
        self.connect()
        self.cabinet._act('maintenance', {})
        self.cabinet._act('audio', {'volume_percent': 200})
        self.assertEqual(self.cabinet.audio.volume_percent, 200)
        self.assertEqual(self.cabinet.configuration()['AUDIO_VOLUME_PERCENT'], '200')
        saved = json.loads((self.root / 'runtime-settings.json').read_text())
        self.assertEqual(saved['AUDIO_VOLUME_PERCENT'], 200)
        for value in (-1, 401, True, float('nan')):
            with self.assertRaises(ValueError):
                self.cabinet._act('audio', {'volume_percent': value})

    def test_health_retries_require_five_distinct_failed_receipts(self):
        self.connect()
        self.cabinet.health_retry_at = 0
        self.controller.mask = 15
        for attempt in range(1, 6):
            now = attempt * 4
            self.cabinet._poll_health(now)
            self.cabinet._poll_health(now + .1)
            self.assertEqual(self.cabinet.health_failures, attempt)
            self.cabinet._poll_health(now + .2)
            self.assertEqual(self.cabinet.health_failures, attempt)
            if attempt < 5:
                self.assertIsNone(self.cabinet.fault)
                self.assertTrue(self.cabinet.health()['ready'])
        self.assertEqual(self.cabinet.phase, 'READY')
        self.assertEqual(self.cabinet.health()['phase'], 'WARN')
        self.assertIsNone(self.cabinet.fault)
        self.assertEqual(self.cabinet.actions.get_nowait()[1], 'repair_hardware')

    def test_active_puzzle_warning_does_not_stop_or_repair_outputs(self):
        self.connect()
        game = self.cabinet.game
        game.handle_rfid('002')
        game.state.completed_players = {'001'}
        game.state.hit_progress = 2
        before = game.get_state_dict()
        commands = len(self.controller.records)
        self.controller.mask = 29
        self.cabinet.health_retry_at = 0
        for attempt in range(1, 6):
            self.cabinet._poll_health(attempt * 4)
            self.cabinet._poll_health(attempt * 4 + .1)
        self.assertEqual(game.get_state_dict(), before)
        self.assertFalse(game._stopping)
        self.assertEqual(self.cabinet.health()['warning']['status'], 'RECOVERY_PENDING')
        self.assertTrue(self.cabinet.health()['ready'])
        self.assertTrue(self.cabinet.actions.empty())
        self.assertFalse(any(r['command'] in ('SAFE STOP', 'SENSORS DISABLE', 'HEALTH RECOVER')
                             for r in self.controller.records[commands:]))
        result = self.cabinet._act('recover', {})
        self.assertTrue(result['deferred'])
        self.assertEqual(game.get_state_dict(), before)

    def test_failed_idle_recovery_warns_and_success_keeps_previous_problem(self):
        self.connect()
        self.controller.mask = 29
        self.cabinet._last_probe_report = self.controller.get_diagnostics()['hardware_health']
        self.cabinet._warn_hardware(self.cabinet._last_probe_report)
        result = self.cabinet._act('repair_hardware', {})
        self.assertFalse(result['recovered'])
        self.assertEqual(self.cabinet.health()['warning']['status'], 'RECOVERY_FAILED')
        self.assertIn('Sensor 1', self.cabinet.health()['warning']['message'])
        self.assertTrue(self.cabinet.health()['ready'])
        self.assertIsNone(self.cabinet.fault)
        self.controller.mask = 31
        self.cabinet._act('repair_hardware', {})
        self.assertEqual(self.cabinet.health()['warning']['status'], 'RECOVERED')
        self.assertIn('Sensor 1', self.cabinet.health()['warning']['message'])
        self.assertEqual(self.cabinet.health()['status'], 'ok')

    def test_show_repair_preserves_outputs_tickets_and_does_not_wait_for_event_lock(self):
        self.connect()
        game = self.cabinet.game
        game.state.active_player = '002'
        game.state.ticket_status = 'DISPENSING'
        game._show_active = True
        game._show_raised = {0, 3}
        before = game.get_state_dict()
        count = len(self.controller.records)
        results = []
        # The show owns this lock in the game event thread. Repair must run now.
        with game._event_lock:
            worker = threading.Thread(target=lambda: results.append(self.cabinet._act('repair_hardware', {})))
            worker.start()
            worker.join(timeout=1)
            self.assertFalse(worker.is_alive())
        self.assertTrue(results[0]['recovered'])
        self.assertEqual(game.get_state_dict(), before)
        self.assertEqual(game._show_raised, {0, 3})
        commands = [r['command'] for r in self.controller.records[count:]]
        self.assertEqual(commands, ['HEALTH RECOVER KEEP_OUTPUTS'])
        self.assertNotIn('TICKET 7', self.controller.commands)
        self.assertFalse(game._hardware_paused)

    def test_timeouts_warn_despite_successful_health_probe(self):
        self.connect()
        original = self.controller.get_diagnostics
        self.controller.get_diagnostics = lambda: {**original(), 'i2c_timeout_count': 12}
        self.cabinet.health_retry_at = 0
        self.cabinet._poll_health(0)
        self.cabinet._poll_health(.1)
        self.assertEqual(self.cabinet.health()['warning']['status'], 'INTERMITTENT')
        self.assertIn('12 new I2C timeouts', self.cabinet.health()['warning']['message'])
        self.assertTrue(self.cabinet.health()['ready'])
        self.cabinet._poll_health(11)
        self.cabinet._poll_health(11.1)
        self.assertEqual(self.cabinet.health()['warning']['status'], 'RECOVERED')

    def test_recovery_preserves_player_progress_and_same_controller(self):
        self.connect()
        self.cabinet.game.handle_rfid('002')
        self.cabinet.game.state.completed_players = {'001'}
        self.cabinet.game.state.hit_progress = 2
        game, state, controller = self.cabinet.game, self.cabinet.game.state, self.cabinet.arduino
        before = game.get_state_dict()
        self.cabinet.latch_fault('temporary sensor loss')
        result = self.cabinet._act('repair_hardware', {})
        self.assertTrue(result['game_preserved'])
        self.assertIs(self.cabinet.game, game)
        self.assertIs(game.state, state)
        self.assertIs(self.cabinet.arduino, controller)
        self.assertEqual(game.get_state_dict(), before)
        self.assertIsNone(self.cabinet.fault)
        self.assertEqual(self.cabinet.phase, 'READY')
        self.assertFalse(game._stopping)
        self.assertIn('HEALTH RECOVER', [r['command'] for r in controller.records])
        self.assertNotIn('TICKET 7', controller.commands)

    def test_fault_flashes_all_moles_and_player_strip_red(self):
        self.connect()
        self.cabinet.latch_fault('test fault')
        self.cabinet._flash_fault(100)
        commands = [r['command'] for r in self.controller.records]
        for mole in range(5):
            self.assertIn(f'LIGHT {mole} 255 0 0', commands)
        self.assertIn('PLAYER_LIGHTS 255 0 0', commands)
        self.cabinet._flash_fault(100.5)
        self.assertEqual(self.controller.records[-1]['command'], 'PLAYER_LIGHTS 0 0 0')

    def test_successful_health_retry_clears_streak_and_returns_to_ten_seconds(self):
        self.connect()
        self.cabinet.health_retry_at = 0
        self.controller.mask = 15
        self.cabinet._poll_health(100)
        self.cabinet._poll_health(100.1)
        self.assertEqual(self.cabinet.health_failures, 1)
        count = len(self.controller.records)
        self.cabinet._poll_health(102)
        self.assertEqual(len(self.controller.records), count)
        self.controller.mask = 31
        self.cabinet._poll_health(103.2)
        self.cabinet._poll_health(103.3)
        self.assertEqual(self.cabinet.health_failures, 0)
        self.assertAlmostEqual(self.cabinet.health_retry_at, 113.3)
        self.assertIsNone(self.cabinet.fault)
