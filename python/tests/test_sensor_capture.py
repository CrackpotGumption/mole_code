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

    def test_capture_routes_hits_while_preserving_badges(self):
        controller = self.controller
        controller.begin_sensor_capture()
        controller._queue_event('ACCEL 0 1 0 0 -10000', 10)
        controller._queue_event('HIT 1 0 18000', 11)
        controller._queue_event('RFID 003', 12)
        self.assertEqual(controller.read_captured_samples(),
                         [('ACCEL 0 1 0 0 -10000', 10), ('HIT 1 0 18000', 11)])
        self.assertEqual(controller.event_queue.get_nowait(), ('RFID 003', 12))
        controller._queue_event('ACCEL 2 2 0 0 -10000', 13)
        controller.end_sensor_capture()
        self.assertEqual(controller.read_captured_samples(), [])
        controller._queue_event('ACCEL 3 4 0 0 -10000', 14)
        self.assertEqual(controller.event_queue.get_nowait(), ('ACCEL 3 4 0 0 -10000', 14))

    def test_capture_is_bounded_and_retains_recent_samples(self):
        controller = self.controller
        controller.begin_sensor_capture()
        for timestamp in range(5):
            controller._queue_event('ACCEL 0 1 0 0 -10000', timestamp)
        self.assertEqual([timestamp for _, timestamp in controller.read_captured_samples()], [3, 4])

    def test_ticket_completion_is_not_dropped_by_sensor_flood(self):
        controller = self.controller
        controller.begin_sensor_capture()
        controller._queue_event('TICKET_DONE 8', 0)
        for timestamp in range(10):
            controller._queue_event('ACCEL 0 1 0 0 -10000', timestamp)
        samples = controller.read_captured_samples()
        self.assertIn(('TICKET_DONE 8', 0), samples)
        self.assertEqual(len(samples), 3)
