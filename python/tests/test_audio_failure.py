import contextlib
import io
from pathlib import Path
import random
import unittest
from unittest.mock import Mock, patch

from app.audio_cues import failure_mix, read_samples, SAMPLE_RATE
from app.mole_game import MoleGame, MOLE_ID_BY_NAME
from test_runtime import Hardware


class Clock:
    def __init__(self):
        self.now = 100.0

    def sleep(self, seconds):
        self.now += seconds


class AudioFailureTests(unittest.TestCase):
    def setUp(self):
        self.hardware = Hardware()
        self.audio = Mock()
        self.game = MoleGame(self.hardware, audio=self.audio)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_start_and_accepted_hit_cues(self):
        self.game.handle_rfid('001')
        self.audio.play.assert_called_with('game_start')
        self.game.handle_hit(MOLE_ID_BY_NAME[self.game.state.whack_order[0]])
        self.audio.play.assert_called_with('mole_hit')
        self.game.state.locked = True
        count = self.audio.play.call_count
        self.game.handle_hit(0)
        self.assertEqual(self.audio.play.call_count, count)

    def test_failure_default_15_seconds_then_same_puzzle(self):
        self.game.handle_rfid('001')
        colors = dict(self.game.state.bug_colors)
        self.game.state.completed_players.add('002')
        start = len(self.hardware.commands)
        clock = Clock()
        with patch('app.mole_game.time.monotonic', side_effect=lambda: clock.now), \
                patch('app.mole_game.time.sleep', side_effect=clock.sleep):
            self.game.handle_hit(MOLE_ID_BY_NAME[self.game.state.queen])
        self.assertAlmostEqual(clock.now, 115)
        self.audio.play_failure.assert_called_once_with(15)
        self.assertEqual(self.game.state.active_player, '001')
        self.assertEqual(self.game.state.completed_players, {'002'})
        self.assertEqual(self.game.state.bug_colors, colors)
        self.assertEqual(self.game.state.hit_progress, 0)
        self.assertEqual(self.game.state.status, 'PLAYING')
        commands = self.hardware.commands[start:]
        animation = commands[commands.index('LIGHTS OFF') + 1:]
        active = set()
        moves = 0
        for command in animation:
            if command == 'MOLES ALL DOWN':
                break
            if command.startswith('MOLE '):
                _, mole, action = command.split()
                if action == 'UP':
                    active.add(mole)
                    moves += 1
                else:
                    active.discard(mole)
                self.assertLessEqual(len(active), 3)
        self.assertGreater(moves, 3)

    def test_duration_configuration_and_cancel(self):
        for duration in (0, 1.25):
            game = MoleGame(self.hardware, audio=self.audio, failure_seconds=duration)
            clock = Clock()
            with patch('app.mole_game.time.monotonic', side_effect=lambda: clock.now), \
                    patch('app.mole_game.time.sleep', side_effect=clock.sleep):
                game.run_failure_show()
            self.assertAlmostEqual(clock.now, 100 + duration)
        with self.assertRaises(ValueError):
            MoleGame(self.hardware, failure_seconds=-1)
        with self.assertRaises(ValueError):
            MoleGame(self.hardware, failure_seconds=float('nan'))
        self.game.handle_rfid('001')
        self.game.stop_requested = lambda: True
        self.hardware.commands.clear()
        self.game.handle_wrong_hit('FRASIER', 'NILES')
        self.assertTrue(self.game.state.locked)
        self.assertNotIn('SENSORS ENABLE', self.hardware.commands)

    def test_placeholders_and_overlapping_mix(self):
        directory = Path(__file__).resolve().parents[1] / 'app' / 'sounds'
        # In-image tests use the installed assets.
        if not directory.exists():
            import app.audio_cues
            directory = Path(app.audio_cues.__file__).parent / 'sounds'
        for name in ('game_start', 'mole_hit', 'failure', 'laugh_1', 'laugh_2', 'laugh_3'):
            self.assertGreater(len(read_samples(directory / f'{name}.wav')), 0)
        samples = failure_mix(directory, 2, random.Random(1))
        self.assertEqual(len(samples), 2 * SAMPLE_RATE * 2)
        self.assertNotEqual(samples, bytes(len(samples)))
