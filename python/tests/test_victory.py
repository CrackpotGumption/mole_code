import contextlib
import io
from pathlib import Path
import random
import unittest
from unittest.mock import Mock, patch

from app.audio_cues import failure_mix, reaction_mix, SAMPLE_RATE
from app.mole_game import MoleGame, PLAYER_IDS
from test_audio_failure import Clock
from test_runtime import Hardware


class VictoryTests(unittest.TestCase):
    def setUp(self):
        self.hardware = Hardware()
        self.audio = Mock()
        self.audio.play_victory_hit.return_value = 0.2
        self.game = MoleGame(self.hardware, audio=self.audio)
        self.game.state.completed_players = set(PLAYER_IDS)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_45_second_victory_reports_tickets_without_hit_polling(self):
        clock = Clock()
        captured = []
        timing = []
        original = self.hardware.send

        def send(command, **kwargs):
            original(command)
            timing.append((clock.now, command))
            if command == 'TICKET 7':
                captured.extend([('TICKET_START 7', clock.now),
                                 ('TICKET_COUNT 7', clock.now), ('TICKET_DONE 7', clock.now)])
            if command == 'MOLE 0 UP':
                captured.extend([('ACCEL 0 0 0 0 -12000', clock.now + 0.01),
                                 ('ACCEL 0 0 0 0 -13000', clock.now + 0.015)])

        def samples():
            result = list(captured)
            captured.clear()
            return result

        self.hardware.send = send
        self.hardware.read_captured_samples = samples
        # Prevent subsequent random motion from repeatedly selecting the test mole.
        with patch('app.mole_game.time.monotonic', side_effect=lambda: clock.now), \
                patch('app.mole_game.time.sleep', side_effect=clock.sleep), \
                patch('app.mole_game.random.sample', side_effect=[[0]] + [[1]] * 100), \
                patch('app.mole_game.random.choice', side_effect=lambda items: items[0]):
            self.game.complete_full_game()
        self.assertAlmostEqual(clock.now, 145)
        self.audio.play_victory.assert_called_once_with(45)
        self.audio.play_victory_hit.assert_not_called()
        self.audio.play_failure_hit.assert_not_called()
        self.assertNotIn('SENSORS ENABLE', self.hardware.commands)
        self.assertIn('SENSORS DISABLE', self.hardware.commands)
        self.assertEqual(self.game.state.completed_players, set())
        self.assertEqual(self.game.state.status, 'WAITING FOR BADGE')
        self.assertEqual(self.game.state.ticket_status, 'NOT REQUESTED')
        self.assertEqual(self.game.state.tickets_dispensed, 0)
        for player in range(6):
            rgb = [command for command in self.hardware.commands
                   if command.startswith(f'PLAYER_LIGHT {player} ') and len(command.split()) == 5]
            self.assertGreater(len(set(rgb)), 2)
            self.assertIn(f'PLAYER_LIGHT {player} GREEN', self.hardware.commands)
        self.game.complete_full_game()
        self.assertEqual(self.hardware.commands.count('TICKET 7'), 1)
        self.audio.play_victory.assert_called_once()
        self.game.handle_rfid('001')
        self.assertEqual(self.game.state.active_player, '001')
        self.assertEqual(self.game.state.status, 'PLAYING')
        self.assertFalse(self.game.state.ticket_dispensed)

    def test_ticket_timeout_and_configuration(self):
        self.game.handle_arduino_event('TICKET_START 7')
        self.game.handle_arduino_event('TICKET_COUNT 3')
        self.game.handle_arduino_event('TICKET_ERROR TIMEOUT 3')
        self.assertEqual(self.game.state.ticket_status, 'ERROR')
        self.assertEqual(self.game.state.tickets_dispensed, 3)
        self.game.handle_arduino_event('TICKET_DONE nope')
        self.assertEqual(self.game.state.ticket_status, 'ERROR')
        with self.assertRaises(ValueError):
            MoleGame(self.hardware, victory_seconds=float('inf'))

    def test_victory_assets_and_whistle_mix(self):
        import app.audio_cues
        directory = Path(app.audio_cues.__file__).parent / 'sounds'
        normal = failure_mix(directory, 2, random.Random(1), victory=True)
        whistle = reaction_mix(directory, 2, 'encouraging_whistle', victory=True)
        self.assertEqual(len(normal), 2 * SAMPLE_RATE * 2)
        self.assertEqual(len(whistle), len(normal))
        self.assertNotEqual(whistle, normal)
