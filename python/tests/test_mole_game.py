import contextlib
import io
import unittest
from unittest.mock import patch

from app.mole_game import MoleGame, MOLE_BY_ID, MOLE_ID_BY_NAME, PLAYER_IDS


class Hardware:
    def __init__(self):
        self.commands = []

    def begin_sensor_capture(self):
        pass

    def end_sensor_capture(self):
        pass

    def read_captured_samples(self):
        return []

    def send(self, command, quiet=False):
        self.commands.append(command)

    def wait_until_idle(self):
        pass


class AccelGameTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        self.hardware = Hardware()
        self.game = MoleGame(self.hardware, victory_seconds=0)
        self.game.handle_rfid("001")

    def sample(self, mole, z=-9000, timestamp=None, channel=None):
        channel = self.game.SENSOR_CHANNELS[mole] if channel is None else channel
        self.game.handle_arduino_event(
            f"ACCEL {mole} {channel} 0 0 {z}", received_at=timestamp)

    def expected(self):
        return MOLE_ID_BY_NAME[self.game.state.whack_order[self.game.state.hit_progress]]

    def test_standard_position_ids_and_each_v2_sensor(self):
        expected = {0: "MARTIN", 1: "DAPHNE", 2: "NILES", 3: "FRASIER", 4: "ROZ"}
        self.assertEqual(MOLE_BY_ID, expected)
        self.assertEqual(self.game.SENSOR_CHANNELS, {mole: mole for mole in range(5)})
        # Test all five IDs through real ACCEL parsing without a wrong-hit reset.
        for mole in range(5):
            self.game.state.whack_order = [expected[mole]]
            self.game.state.hit_progress = 0
            self.game.state.active_player = "001"
            self.game.state.locked = False
            self.game._hit_latched.clear()
            self.game._last_hit.clear()
            with patch.object(self.game, "handle_correct_hit") as correct:
                self.game.handle_arduino_event(f"ACCEL {mole} {mole} 0 0 -9000")
                correct.assert_called_once_with(mole, expected[mole])

    def test_correct_strike_and_retracted_target(self):
        mole = self.expected()
        self.sample(mole)
        self.assertEqual(self.game.state.hit_progress, 1)
        self.assertIn(f"MOLE {mole} DOWN", self.hardware.commands)
        self.sample(mole, -15000)
        self.assertEqual(self.game.state.hit_progress, 1)

    def test_noise_malformed_channel_and_stale_samples(self):
        mole = self.expected()
        for z in (-1900, 9000, -8999, -40000):
            self.sample(mole, z)
        self.sample(mole, timestamp=self.game._accept_samples_after - 1)
        self.sample(mole, channel=99)
        for line in ("ACCEL bad", "ACCEL 2 2 a 0 -9000", "ACCEL 99 2 0 0 -9000"):
            self.game.handle_arduino_event(line)
        self.assertEqual(self.game.state.hit_progress, 0)

    def test_locked_samples(self):
        self.game.state.locked = True
        self.sample(self.expected())
        self.assertEqual(self.game.state.hit_progress, 0)

    @patch("app.mole_game.time.sleep")
    def test_queen_strike_restarts_and_requires_release(self, sleep):
        mole = MOLE_ID_BY_NAME[self.game.state.queen]
        self.sample(mole)
        self.assertEqual(self.game.state.hit_progress, 0)
        count = len(self.hardware.commands)
        self.sample(mole)
        self.assertEqual(len(self.hardware.commands), count)
        self.sample(mole, -1900)
        self.sample(mole, timestamp=self.game._last_hit[mole] + 1)
        self.assertGreater(len(self.hardware.commands), count)

    def test_all_puzzles_complete_and_ticket_requested_once(self):
        sample_time = self.game._accept_samples_after
        for player in PLAYER_IDS:
            self.game.handle_rfid(player)
            for _ in range(4):
                sample_time += 1
                self.sample(self.expected(), -1900, timestamp=sample_time)
                self.sample(self.expected(), timestamp=sample_time + 0.1)
        self.assertEqual(self.game.state.completed_players, set())
        self.assertEqual(self.game.state.status, "WAITING FOR BADGE")
        self.game.complete_full_game()
        self.assertEqual(self.hardware.commands.count("TICKET 7"), 1)

    @patch("app.mole_game.time.sleep")
    def test_cooldown_even_after_release(self, sleep):
        mole = MOLE_ID_BY_NAME[self.game.state.queen]
        now = self.game._accept_samples_after + 1
        self.sample(mole, timestamp=now)
        self.sample(mole, -1900, timestamp=now + 0.1)
        count = len(self.hardware.commands)
        self.sample(mole, timestamp=now + 0.2)
        self.assertEqual(len(self.hardware.commands), count)
        self.sample(mole, timestamp=now + 0.4)
        self.assertGreater(len(self.hardware.commands), count)

    def test_puzzle_arms_once_and_rearms_after_correct_hit(self):
        self.assertEqual(self.hardware.commands[-1], "SENSORS PUZZLE")
        mole = self.expected()
        self.game.handle_arduino_event(f"HIT {mole} {mole} 12000")
        self.assertEqual(self.game.state.hit_progress, 1)
        self.assertEqual(self.hardware.commands[-1], "SENSORS PUZZLE")
        self.assertEqual(self.hardware.commands.count("SENSORS PUZZLE"), 2)
        # A sample from the prior arm cannot advance another target.
        next_mole = self.expected()
        self.game.handle_arduino_event(f"HIT {next_mole} {next_mole} 12000",
                                      received_at=self.game._accept_samples_after - 1)
        self.assertEqual(self.game.state.hit_progress, 1)

    def test_immediate_hit_after_arm_is_not_lost(self):
        def drain():
            # Model a reader receiving a HIT as soon as the arming ACK arrives.
            if self.hardware.commands[-1] == "SENSORS PUZZLE":
                self.received = 101
        with patch('app.mole_game.time.monotonic', side_effect=[100, 102]),                 patch.object(self.hardware, 'wait_until_idle', side_effect=drain):
            self.game._resume_hit_detection()
        mole = self.expected()
        self.game.handle_arduino_event(f"HIT {mole} {mole} 12000", received_at=self.received)
        self.assertEqual(self.game.state.hit_progress, 1)

    def test_legacy_hit(self):
        mole = self.expected()
        self.game.handle_arduino_event(f"HIT {mole} {self.game.SENSOR_CHANNELS[mole]} 18000")
        self.assertEqual(self.game.state.hit_progress, 1)
