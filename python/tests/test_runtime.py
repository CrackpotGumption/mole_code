import contextlib
import io
import signal
import sys
import types
import unittest
from unittest.mock import patch

from app import app
from app.mole_game import MoleGame


class Hardware:
    def __init__(self, **kwargs):
        self.running = True
        self.commands = []
        self.event_handler = None
        self.closed = False
        self.drained = False

    def begin_sensor_capture(self):
        pass

    def end_sensor_capture(self):
        pass

    def read_captured_samples(self):
        return []

    def send(self, command, quiet=False):
        self.commands.append(command)

    def wait_until_idle(self, timeout=5):
        self.drained = True

    def close(self):
        self.closed = True


class RuntimeTests(unittest.TestCase):
    def run_main(self, bind_error=False):
        events = []
        class Cabinet:
            def __init__(self, *args):
                events.append('cabinet-created')
            def start(self):
                events.append('hardware-start')
                signal.raise_signal(signal.SIGTERM)
            def tick(self):
                pass
            def close(self):
                events.append('cabinet-closed')
        class Status:
            def __init__(self, *args, **kwargs):
                if bind_error:
                    raise OSError('address in use')
            def start(self):
                events.append('http-start')
            def stop(self):
                events.append('http-stopped')
        modules = {
            'app.cabinet': types.SimpleNamespace(Cabinet=Cabinet),
            'app.hardware': types.SimpleNamespace(ArduinoController=lambda **kwargs: None),
            'app.status_service': types.SimpleNamespace(StatusService=Status),
        }
        with patch.dict(sys.modules, modules), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = app.main()
        return result, events

    def test_http_starts_before_hardware_and_sigterm_closes_services(self):
        previous = signal.getsignal(signal.SIGTERM)
        result, events = self.run_main()
        self.assertEqual(result, 0)
        self.assertLess(events.index('http-start'), events.index('hardware-start'))
        self.assertIn('cabinet-closed', events)
        self.assertIn('http-stopped', events)
        self.assertIs(signal.getsignal(signal.SIGTERM), previous)

    def test_http_bind_failure_closes_runtime(self):
        result, events = self.run_main(bind_error=True)
        self.assertEqual(result, 1)
        self.assertIn('cabinet-closed', events)
        self.assertNotIn('hardware-start', events)

    def test_shutdown_blocks_late_badge_and_accel_events(self):
        hardware = Hardware()
        game = MoleGame(hardware)
        game.retract_game()
        commands = list(hardware.commands)
        game.handle_rfid('001')
        game.handle_arduino_event('RFID 002')
        game.handle_arduino_event('ACCEL 2 2 0 0 -12000')
        self.assertIsNone(game.state.active_player)
        self.assertEqual(hardware.commands, commands)
