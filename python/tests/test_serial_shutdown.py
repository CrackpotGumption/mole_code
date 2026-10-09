import queue
import threading
import unittest
from unittest.mock import patch
from test_sensor_capture import ArduinoController


class BlockingPort:
    port, baudrate = '/dev/test', 115200
    def __init__(self, ready=False):
        self.initial = queue.Queue()
        if ready:
            self.initial.put(b'PROTOCOL 2\n')
            self.initial.put(b'READY\n')
        self.reading = threading.Event()
        self.cancelled = threading.Event()
        self.read_finished = threading.Event()
        self.closed_after_read = False
    def readline(self):
        try:
            return self.initial.get_nowait()
        except queue.Empty:
            self.reading.set()
            self.cancelled.wait(2)
            self.read_finished.set()
            # Matches pyserial's fd=None shutdown failure.
            raise TypeError("'NoneType' object cannot be interpreted as an integer")
    def cancel_read(self):
        self.cancelled.set()
    def close(self):
        self.closed_after_read = self.read_finished.is_set()


class SerialShutdownTests(unittest.TestCase):
    def test_startup_timeout_cancels_and_joins_reader_before_closing(self):
        port = BlockingPort()
        module = ArduinoController.__init__.__globals__['serial']
        with patch.object(module, 'Serial', return_value=port, create=True), patch.object(module, 'SerialException', OSError, create=True), patch('threading.excepthook') as uncaught:
            with self.assertRaisesRegex(TimeoutError, 'did not report READY'):
                ArduinoController(ready_timeout=0.02)
            uncaught.assert_not_called()
        self.assertTrue(port.closed_after_read)

    def test_active_read_failure_is_recorded_instead_of_uncaught(self):
        port = BlockingPort(ready=True)
        module = ArduinoController.__init__.__globals__['serial']
        with patch.object(module, 'Serial', return_value=port, create=True), patch.object(module, 'SerialException', OSError, create=True), patch('threading.excepthook') as uncaught:
            controller = ArduinoController(ready_timeout=0.2)
            try:
                self.assertTrue(port.reading.wait(1))
                port.cancelled.set()
                controller.reader.join(1)
                self.assertFalse(controller.running)
                self.assertIn('SERIAL READ ERROR', controller.failure_reason)
                self.assertTrue(controller.get_diagnostics()['recent_errors'])
                uncaught.assert_not_called()
            finally:
                controller.close()
