import importlib
import queue
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

try:
    from app.hardware import ArduinoController
except ModuleNotFoundError as error:
    if error.name != 'serial':
        raise
    # No serial port is opened; host tests only exercise event routing.
    with patch.dict(sys.modules, {'serial': types.ModuleType('serial')}):
        ArduinoController = importlib.import_module('app.hardware').ArduinoController


class SensorCaptureTests(unittest.TestCase):
    def setUp(self):
        self.controller = ArduinoController.__new__(ArduinoController)
        self.controller._capture_lock = threading.Lock()
        self.controller._sensor_capture = False
        self.controller._captured_samples = queue.Queue(maxsize=2)
        self.controller._captured_ticket_events = queue.Queue()
        self.controller.event_queue = queue.Queue()
        self.controller.event_handler = Mock()

    def test_zero_sample_streak_and_trace_retention(self):
        from collections import deque
        c = self.controller
        c._diagnostic_lock = threading.Lock()
        c._serial_line_count = 0
        c._recent_serial = deque(maxlen=100)
        c._hit_traces = deque(maxlen=250)
        c._last_sensor_values = {}
        c._last_sensor_at = {}
        c._sensor_zero_streak = {}
        for _ in range(3):
            c._record_serial('SAMPLE 3 0 0 0')
        self.assertEqual(c._sensor_zero_streak[3], 3)
        c._record_serial('SAMPLE 3 1 2 -2000')
        self.assertEqual(c._sensor_zero_streak[3], 0)
        c._record_serial('HIT_TRACE MOLE 3 REASON CANDIDATE')
        for _ in range(110):
            c._record_serial('OK KEEPALIVE')
        self.assertEqual(len(c._hit_traces), 1)
        self.assertEqual(len(c._recent_serial), 100)

    def test_capture_routes_hits_while_preserving_badges(self):
        controller = self.controller
        controller.begin_sensor_capture()
        controller._queue_event('ACCEL 0 0 0 0 -10000', 10)
        controller._queue_event('HIT 1 1 18000', 11)
        controller._queue_event('RFID 003', 12)
        self.assertEqual(controller.read_captured_samples(),
                         [('ACCEL 0 0 0 0 -10000', 10), ('HIT 1 1 18000', 11)])
        self.assertEqual(controller.event_queue.get_nowait(), ('RFID 003', 12))
        controller._queue_event('ACCEL 2 2 0 0 -10000', 13)
        controller.end_sensor_capture()
        self.assertEqual(controller.read_captured_samples(), [])
        controller._queue_event('ACCEL 3 3 0 0 -10000', 14)
        self.assertEqual(controller.event_queue.get_nowait(), ('ACCEL 3 3 0 0 -10000', 14))

    def test_capture_is_bounded_and_retains_recent_samples(self):
        controller = self.controller
        controller.begin_sensor_capture()
        for timestamp in range(5):
            controller._queue_event('ACCEL 0 0 0 0 -10000', timestamp)
        self.assertEqual([timestamp for _, timestamp in controller.read_captured_samples()], [3, 4])

    def test_ticket_completion_is_not_dropped_by_sensor_flood(self):
        controller = self.controller
        controller.begin_sensor_capture()
        controller._queue_event('TICKET_DONE 8', 0)
        for timestamp in range(10):
            controller._queue_event('ACCEL 0 0 0 0 -10000', timestamp)
        samples = controller.read_captured_samples()
        self.assertIn(('TICKET_DONE 8', 0), samples)
        self.assertEqual(len(samples), 3)

    def test_reader_does_not_log_raw_samples_by_default(self):
        controller = self.controller
        controller.running = True
        controller.log_raw_accel = False
        controller.command_ack = threading.Event()
        lines = [b'ACCEL 0 0 0 0 -9000\n', b'OK SENSORS PUZZLE ARMED\n']

        class Port:
            def readline(self):
                if lines:
                    return lines.pop(0)
                controller.running = False
                return b''

        controller.serial = Port()
        with patch('builtins.print') as output:
            controller._reader_loop()
        output.assert_called_once_with('<< OK SENSORS PUZZLE ARMED')
        self.assertTrue(controller.command_ack.is_set())

    def test_first_ack_timeout_stops_writer_and_rejects_more_commands(self):
        controller = self.controller
        controller.running = True
        controller.failure_reason = None
        controller.serial = Mock()
        controller.command_ack = Mock()
        controller.command_ack.wait.return_value = False
        controller.command_queue = queue.Queue()
        controller.command_queue.put('MOLE 3 DOWN')
        controller.command_queue.put('MOLE 4 UP')
        with patch('builtins.print'):
            controller._writer_loop()
        self.assertFalse(controller.running)
        self.assertEqual(controller.failure_reason, 'ACK TIMEOUT: MOLE 3 DOWN')
        controller.serial.write.assert_called_once_with(b'MOLE 3 DOWN\n')
        self.assertEqual(controller.command_queue.qsize(), 1)
        with self.assertRaises(RuntimeError):
            controller.send('LIGHTS OFF')
        with self.assertRaises(RuntimeError):
            controller.wait_until_idle()

    def test_quiet_rainbow_ack_and_heartbeat_keep_errors_visible(self):
        controller = self.controller
        controller.running = True
        controller.log_raw_accel = False
        controller.log_heartbeat = False
        controller._quiet_command_ack = True
        controller.command_ack = threading.Event()
        lines = [b'HEARTBEAT 1000 LOOPS 10 SENSORS DISABLED\n',
                 b'OK LIGHT 0 255 0 0\n', b'ERROR BAD LIGHT\n']

        class Port:
            def readline(self):
                if lines:
                    return lines.pop(0)
                controller.running = False
                return b''

        controller.serial = Port()
        with patch('builtins.print') as output:
            controller._reader_loop()
        output.assert_called_once_with('<< ERROR BAD LIGHT')
        self.assertTrue(controller.command_ack.is_set())

    def test_startup_waits_for_ready_before_starting_writer(self):
        serial_module = ArduinoController.__init__.__globals__["serial"]
        events = []

        class Controller(ArduinoController):
            def _reader_loop(self):
                events.append('boot')
                self._ready_event.set()

            def _writer_loop(self):
                events.append('writer')

            def _event_loop(self):
                pass

        port = Mock()
        with patch.object(serial_module, 'Serial', return_value=port, create=True):
            controller = Controller(ready_timeout=0.2)
            controller.writer.join(timeout=0.2)
            controller.close()
        self.assertEqual(events, ['boot', 'writer'])

    def test_missing_ready_closes_port_without_sending_commands(self):
        serial_module = ArduinoController.__init__.__globals__["serial"]

        class Controller(ArduinoController):
            def _reader_loop(self):
                pass

        port = Mock()
        with patch.object(serial_module, 'Serial', return_value=port, create=True):
            with self.assertRaisesRegex(TimeoutError, 'did not report READY'):
                Controller(ready_timeout=0.01)
        port.close.assert_called_once()
        port.write.assert_not_called()

    def test_firmware_mismatch_closes_before_game_workers_start(self):
        from app.firmware import FirmwareMismatch
        serial_module = ArduinoController.__init__.__globals__['serial']
        started = []

        class Controller(ArduinoController):
            def _reader_loop(self):
                self.firmware_identity = 'FIRMWARE old 1.0 oldhash'
                self._ready_event.set()

            def _writer_loop(self):
                started.append('writer')

            def _event_loop(self):
                started.append('events')

        port = Mock()
        with patch.object(serial_module, 'Serial', return_value=port, create=True):
            with self.assertRaises(FirmwareMismatch):
                Controller(ready_timeout=0.2, expected_firmware='FIRMWARE new 2.1 newhash')
        port.close.assert_called_once()
        port.write.assert_not_called()
        self.assertEqual(started, [])

    def test_serial_diagnostics_capture_hardware_reports_and_errors(self):
        serial_module = ArduinoController.__init__.__globals__['serial']

        class Controller(ArduinoController):
            def _reader_loop(self):
                for line in ('SENSOR OK 0 CHANNEL 0', 'SENSOR MISSING 2 CHANNEL 2',
                             'RFID_DIAG ERROR READER_NOT_RESPONDING', 'I2C_TIMEOUT',
                             'ERROR BAD MOLE'):
                    self._record_serial(line)
                self._ready_event.set()

            def _writer_loop(self):
                pass

            def _event_loop(self):
                pass

        port = Mock(port='/dev/mega', baudrate=115200)
        with patch.object(serial_module, 'Serial', return_value=port, create=True):
            controller = Controller(ready_timeout=0.2)
            report = controller.get_diagnostics()
            controller.close()
        self.assertEqual(report['sensors']['0']['startup_status'], 'OK')
        self.assertEqual(report['sensors']['2']['startup_status'], 'MISSING')
        self.assertEqual(report['rfid_status_at_last_report'], 'NOT_RESPONDING')
        self.assertEqual(report['i2c_timeout_count'], 1)
        self.assertEqual(report['last_ack'], 'ERROR BAD MOLE')
        self.assertEqual(len(report['recent_errors']), 4)
