import array
from pathlib import Path
import random
import tempfile
import unittest
import wave
from unittest.mock import Mock

from app.audio_cues import AudioCues, category_mix, select_audio_device, SAMPLE_RATE
from app.mole_game import MoleGame, MOLE_ID_BY_NAME
from test_runtime import Hardware


class FxCategoryTests(unittest.TestCase):
    def test_category_selection_and_cheers_alias(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for category in ('hit', 'cheers', 'victory'):
                (root / category).mkdir()
                (root / category / 'one.wav').touch()
                (root / category / 'two.wav').touch()
            audio = AudioCues.__new__(AudioCues)
            audio.fx_directory = root
            for cue, category in (('mole_hit', 'hit'), ('cheer', 'cheers'), ('victory', 'victory')):
                selected = audio.choose_cue(cue)
                self.assertTrue(selected.startswith('asset:'))
                self.assertEqual(Path(selected.split(':', 1)[1]).parent.name, category)
            self.assertEqual(audio.choose_cue('game_start'), 'game_start')

    def test_laugh_mix_limits_volume_and_has_exact_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'laugh.wav'
            with wave.open(str(path), 'wb') as target:
                target.setparams((1, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
                target.writeframes(array.array('h', [30000] * SAMPLE_RATE).tobytes())
            for voices in (2, 3):
                result = category_mix([path], 2, random.Random(1), voices=voices)
                samples = array.array('h')
                samples.frombytes(result)
                self.assertEqual(len(samples), 2 * SAMPLE_RATE)
                self.assertLessEqual(max(samples), 24000)
                self.assertGreater(max(samples), 0)

    def test_completed_puzzle_plays_cheer_on_return_to_idle(self):
        audio = Mock()
        game = MoleGame(Hardware(), audio=audio)
        game.handle_rfid('001')
        for _ in range(4):
            game.handle_hit(MOLE_ID_BY_NAME[game.state.whack_order[game.state.hit_progress]])
        audio.play.assert_called_with('cheer')
        self.assertEqual(game.state.status, 'WAITING FOR BADGE')

    def test_usb_selection_is_by_card_name_and_can_be_forced(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(select_audio_device('default', root)[0], 'default')
            self.assertIn('No USB', select_audio_device('usb', root)[2])
            card = root / 'card2'
            card.mkdir()
            (card / 'id').write_text('USBspeaker')
            (card / 'usbid').write_text('1234:5678')
            self.assertEqual(select_audio_device('default', root)[0], 'plughw:CARD=USBspeaker,DEV=0')
            self.assertEqual(select_audio_device('usb', root)[0], 'plughw:CARD=USBspeaker,DEV=0')
            self.assertEqual(select_audio_device('hw:CARD=Other,DEV=0', root)[0], 'hw:CARD=Other,DEV=0')
            other = root / 'card3'
            other.mkdir()
            (other / 'id').write_text('OtherUSB')
            (other / 'usbid').write_text('9876:5432')
            self.assertIn('Multiple USB', select_audio_device('usb', root)[2])

    def test_alsa_usb_fallback_when_proc_asound_is_missing(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            listing = Mock(stdout='card 0: PCH [HDA Intel PCH], device 0: Analog [Analog]\ncard 1: AUDIO [USB  AUDIO], device 0: USB Audio [USB Audio]\n')
            info = Mock(stdout="Mixer name: 'USB Mixer'")
            with patch('app.audio_cues.subprocess.run', side_effect=[listing, Mock(stdout="Mixer name: 'Realtek'"), info]):
                device, cards, error = select_audio_device('usb', Path(folder))
            self.assertEqual(device, 'plughw:CARD=AUDIO,DEV=0')
            self.assertEqual(cards[0]['discovery'], 'ALSA')
            self.assertIsNone(error)

    def test_legacy_default_does_not_fall_back_to_builtin_speaker(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            listing = Mock(stdout='card 0: PCH [HDA Intel PCH], device 0: Analog [Analog]\n')
            with patch('app.audio_cues.subprocess.run', side_effect=[listing, Mock(stdout="Realtek")]):
                _, cards, error = select_audio_device('default', Path(folder))
            self.assertEqual(cards, [])
            self.assertIn('No USB audio', error)
