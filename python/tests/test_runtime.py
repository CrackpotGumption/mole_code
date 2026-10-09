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
    def run_main(self, mode):
        hardware = Hardware()

        class Status:
            def __init__(self, game, **kwargs):
                if mode == 'bind-error':
                    raise OSError('address in use')
                self.game = game
                self.stopped = False

            def start(self):
                if mode == 'disconnect':
                    hardware.running = False
                else:
                    signal.raise_signal(signal.SIGTERM)

            def stop(self):
                self.stopped = True

        services = []

        def make_status(*args, **kwargs):
            service = Status(*args, **kwargs)
            services.append(service)
            return service

        modules = {
            'app.hardware': types.SimpleNamespace(ArduinoController=lambda **kwargs: hardware),
            'app.status_service': types.SimpleNamespace(StatusService=make_status),
        }
        with patch.dict(sys.modules, modules), patch.dict('os.environ', {'GAME_STATE_PATH': ''}), patch('app.app.threading.Thread'), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = app.main()
        return result, hardware, services

    def test_sigterm_retracts_and_drains_before_close(self):
        previous = signal.getsignal(signal.SIGTERM)
        result, hardware, services = self.run_main('signal')
        self.assertEqual(result, 0)
        self.assertEqual(hardware.commands[:4],
                         ['SENSORS DISABLE', 'MOLES ALL DOWN', 'LIGHTS OFF', 'PLAYER_LIGHTS OFF'])
        self.assertEqual(hardware.commands[-4:], hardware.commands[:4])
        self.assertEqual(len([command for command in hardware.commands if command.startswith('LIGHT ')]), 5)
        self.assertTrue(hardware.drained)
        self.assertTrue(hardware.closed)
        self.assertTrue(services[0].stopped)
        self.assertIs(signal.getsignal(signal.SIGTERM), previous)

    def test_disconnection_exits_with_failure(self):
        result, hardware, services = self.run_main('disconnect')
        self.assertEqual(result, 1)
        self.assertTrue(hardware.closed)
        self.assertTrue(services[0].stopped)

    def test_status_startup_failure_cleans_up_hardware(self):
        result, hardware, _ = self.run_main('bind-error')
        self.assertEqual(result, 1)
        self.assertTrue(hardware.closed)
        self.assertIn('MOLES ALL DOWN', hardware.commands)

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
