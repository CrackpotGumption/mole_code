import unittest
from unittest.mock import Mock, patch
from app.audio_cues import maximize_usb_volume, amplify_samples


class VolumeTests(unittest.TestCase):
    def test_only_selected_usb_playback_controls_are_maximized(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            action = args[3]
            if action == 'scontrols':
                output = "Simple mixer control 'Speaker',0\nSimple mixer control 'Mic',0\n"
            elif action == 'sget':
                output = 'Capabilities: pvolume pswitch' if args[4] == 'Speaker,0' else 'Capabilities: cvolume cswitch'
            else:
                output = 'Playback 100 [100%] [on]'
            return Mock(returncode=0, stdout=output, stderr='')
        with patch('app.audio_cues.subprocess.run', side_effect=run):
            report = maximize_usb_volume('plughw:CARD=SpeakerUSB,DEV=0', [{'id': 'SpeakerUSB'}])
        self.assertEqual(report['status'], 'APPLIED')
        setters = [args for args in calls if args[3] == 'sset']
        self.assertEqual(setters, [['amixer', '-c', 'SpeakerUSB', 'sset', 'Speaker,0', '100%', 'unmute']])

    def test_unsupported_or_failed_controls_are_reported(self):
        with patch('app.audio_cues.subprocess.run', return_value=Mock(returncode=0, stdout='', stderr='')):
            self.assertEqual(maximize_usb_volume('plughw:CARD=USB,DEV=0', [{'id': 'USB'}])['status'], 'NO_PLAYBACK_CONTROLS')
        with patch('app.audio_cues.subprocess.run', side_effect=FileNotFoundError('amixer')):
            self.assertEqual(maximize_usb_volume('plughw:CARD=USB,DEV=0', [{'id': 'USB'}])['status'], 'ERROR')
        self.assertEqual(maximize_usb_volume('default', [])['status'], 'NOT_USB')

    def test_boost_attenuation_mute_and_clipping(self):
        self.assertEqual(list(amplify_samples([1000, -1000], 200)[0]), [2000, -2000])
        self.assertEqual(list(amplify_samples([1000, -1000], 50)[0]), [500, -500])
        self.assertEqual(list(amplify_samples([1000, -1000], 0)[0]), [0, 0])
        output, clipped = amplify_samples([30000, -30000], 200)
        self.assertEqual(list(output), [32767, -32768])
        self.assertEqual(clipped, 2)
