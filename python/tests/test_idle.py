import contextlib
import io
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app.app import keyboard_rfid_loop
from app.mole_game import MoleGame, MOLE_ID_BY_NAME, RGB
from app.progress_store import ProgressStore
from test_runtime import Hardware


class IdleRainbowTests(unittest.TestCase):
    def setUp(self):
        self.hardware = Hardware()
        self.game = MoleGame(self.hardware, victory_seconds=0)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_idle_animates_then_badge_uses_puzzle_colors(self):
        with patch('app.mole_game.time.monotonic', return_value=100):
            self.game.restore_hardware()
        first = self.hardware.commands[-5:]
        self.assertTrue(all(command.startswith('LIGHT ') for command in first))
        self.assertNotIn('MOLES ALL UP', self.hardware.commands)
        count = len(self.hardware.commands)
        with patch('app.mole_game.time.monotonic', return_value=100.1):
            self.game.tick_idle()
        self.assertEqual(len(self.hardware.commands), count)
        with patch('app.mole_game.time.monotonic', return_value=102):
            self.game.tick_idle()
        self.assertNotEqual(self.hardware.commands[-5:], first)
        self.game.handle_arduino_event('RFID 001')
        self.assertEqual(self.game.state.status, 'PLAYING')
        for bug, color in self.game.state.bug_colors.items():
            r, g, b = RGB[color]
            self.assertIn(f'LIGHT {MOLE_ID_BY_NAME[bug]} {r} {g} {b}', self.hardware.commands)
        count = len(self.hardware.commands)
        with patch('app.mole_game.time.monotonic', return_value=200):
            self.game.tick_idle()
        self.assertEqual(len(self.hardware.commands), count)

    def test_rainbows_resume_after_player_completion(self):
        self.game.handle_rfid('001')
        for _ in range(4):
            bug = self.game.state.whack_order[self.game.state.hit_progress]
            self.game.handle_hit(MOLE_ID_BY_NAME[bug])
        self.hardware.commands.clear()
        self.game.tick_idle()
        self.assertEqual(len(self.hardware.commands), 5)
        self.assertTrue(all(command.startswith('LIGHT ') for command in self.hardware.commands))
        self.assertEqual(self.game.state.completed_players, {'001'})
        self.assertEqual(self.game.state.status, 'WAITING FOR BADGE')

    def test_completed_recovery_keeps_green_indicators_and_idle_rainbows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'progress.json'
            ProgressStore(path, ('001', '002', '003', '004', '005', '006')).save({'001', '002'}, False)
            game = MoleGame(self.hardware, state_path=path)
            game.restore_hardware()
        self.assertIn('PLAYER_LIGHT 0 GREEN', self.hardware.commands)
        self.assertIn('PLAYER_LIGHT 1 GREEN', self.hardware.commands)
        self.assertTrue(all(command.startswith('LIGHT ') for command in self.hardware.commands[-5:]))

    def test_idle_after_final_victory_does_not_reset_completions(self):
        self.game.state.completed_players = {'001', '002', '003', '004', '005', '006'}
        self.game.state.ticket_dispensed = True
        self.game.complete_full_game()
        self.hardware.commands.clear()
        self.game.tick_idle()
        self.assertEqual(len(self.hardware.commands), 5)
        self.assertEqual(len(self.game.state.completed_players), 6)
        self.assertEqual(self.game.state.status, 'GAME COMPLETE')

    def test_no_idle_frames_during_shows_shutdown_or_busy_queue(self):
        for status in ('SETTING UP ROUND', 'LAUGH AT YOU', 'VICTORY CELEBRATION'):
            self.game.state.status = status
            self.game.tick_idle()
        self.assertEqual(self.hardware.commands, [])
        self.game.state.status = 'WAITING FOR BADGE'
        self.hardware.command_queue = queue.Queue()
        self.hardware.command_queue.put('already queued')
        self.game.tick_idle()
        self.assertEqual(self.hardware.commands, [])
        self.hardware.command_queue.get()
        self.hardware.command_queue.task_done()
        self.game.retract_game()
        self.hardware.commands.clear()
        self.game.tick_idle()
        self.assertEqual(self.hardware.commands, [])

    def test_custom_idle_frame_interval(self):
        game = MoleGame(self.hardware, idle_frame_seconds=4)
        with patch('app.mole_game.time.monotonic', return_value=100):
            game.tick_idle()
        count = len(self.hardware.commands)
        with patch('app.mole_game.time.monotonic', return_value=103.9):
            game.tick_idle()
        self.assertEqual(len(self.hardware.commands), count)
        with patch('app.mole_game.time.monotonic', return_value=104):
            game.tick_idle()
        self.assertEqual(len(self.hardware.commands), count + 5)

    def test_console_badge_formats(self):
        self.hardware.event_queue = queue.Queue()
        with patch('app.app.sys.stdin', io.StringIO('1\n002\nRFID 003\ninvalid\n9\n')):
            keyboard_rfid_loop(self.hardware, threading.Event())
        self.assertEqual([self.hardware.event_queue.get_nowait()[0] for _ in range(3)],
                         ['RFID 001', 'RFID 002', 'RFID 003'])
        self.assertTrue(self.hardware.event_queue.empty())

    def test_console_rfid_diagnostics_use_serial_without_badge_event(self):
        self.hardware.event_queue = queue.Queue()
        with patch('app.app.sys.stdin', io.StringIO('rfid status\nRFID INIT\n')):
            keyboard_rfid_loop(self.hardware, threading.Event())
        self.assertEqual(self.hardware.commands, ['RFID STATUS', 'RFID INIT'])
        self.assertTrue(self.hardware.event_queue.empty())
