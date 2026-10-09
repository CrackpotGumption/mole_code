import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.firmware import FirmwareMismatch, connect_verified, identity_line


class FirmwareTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.bundle = Path(folder.name)
        self.manifest = {'name': 'MOLE_FINAL_NO_INTERVAL_v2', 'version': '2.1.0', 'sha256': 'a' * 64}
        (self.bundle / 'manifest.json').write_text(json.dumps(self.manifest))
        (self.bundle / (self.manifest['name'] + '.ino.hex')).write_text(':00000001FF\n')
        env = patch.dict('os.environ', {'FIRMWARE_DIR': str(self.bundle), 'FIRMWARE_AUTO_FLASH': '1', 'FIRMWARE_HISTORY_PATH': str(self.bundle / 'history.json')})
        env.start()
        self.addCleanup(env.stop)

    def test_matching_sketch_is_not_flashed(self):
        factory = Mock()
        with patch('app.firmware.run') as run:
            self.assertIs(connect_verified(factory, '/dev/mega', 115200), factory.return_value)
        run.assert_not_called()
        factory.assert_called_once_with(port='/dev/mega', baud=115200,
                                        expected_firmware=identity_line(self.manifest))

    def test_mismatch_uploads_and_revalidates(self):
        factory = Mock(side_effect=[FirmwareMismatch('legacy sketch'), 'verified controller'])
        with patch('app.firmware.run') as run:
            self.assertEqual(connect_verified(factory, '/dev/mega', 115200), 'verified controller')
        self.assertEqual(factory.call_count, 2)
        command = run.call_args.args[0]
        self.assertEqual(command[:5], ['avrdude', '-p', 'atmega2560', '-c', 'wiring'])
        self.assertNotIn('-F', command)
        self.assertIn('/dev/mega', command)

    def test_failed_verification_does_not_flash_twice(self):
        factory = Mock(side_effect=FirmwareMismatch('wrong sketch'))
        with patch('app.firmware.run') as run, self.assertRaises(FirmwareMismatch):
            connect_verified(factory, '/dev/mega', 115200)
        run.assert_called_once()

    def test_dead_board_does_not_trigger_flash(self):
        factory = Mock(side_effect=TimeoutError('no READY'))
        with patch('app.firmware.run') as run, self.assertRaises(TimeoutError):
            connect_verified(factory, '/dev/mega', 115200)
        run.assert_not_called()

    def test_auto_flash_can_be_disabled(self):
        factory = Mock(side_effect=FirmwareMismatch('wrong sketch'))
        with patch.dict('os.environ', {'FIRMWARE_AUTO_FLASH': '0'}), patch('app.firmware.run') as run:
            with self.assertRaisesRegex(RuntimeError, 'disabled'):
                connect_verified(factory, '/dev/mega', 115200)
        run.assert_not_called()

    def test_failed_flash_survives_restart_and_is_not_retried_immediately(self):
        factory = Mock(side_effect=FirmwareMismatch('old'))
        with patch('app.firmware.run', side_effect=RuntimeError('bootloader timeout')) as run:
            with self.assertRaisesRegex(RuntimeError, 'bootloader timeout'):
                connect_verified(factory, '/dev/mega', 115200)
            with self.assertRaisesRegex(RuntimeError, 'retry blocked'):
                connect_verified(factory, '/dev/mega', 115200)
        run.assert_called_once()
        saved = json.loads((self.bundle / 'history.json').read_text())
        record = next(iter(saved.values()))
        self.assertEqual(record['attempts'], 1)
        self.assertEqual(record['status'], 'FAILED')
        self.assertEqual(record['last_error'], 'bootloader timeout')

    def test_explicit_force_flash_can_recover_board_without_ready(self):
        factory = Mock(side_effect=[TimeoutError('no READY'), 'verified'])
        with patch('app.firmware.run') as run:
            self.assertEqual(connect_verified(factory, '/dev/mega', 115200, force_flash=True), 'verified')
        run.assert_called_once()

    def test_explicit_retry_works_with_auto_flash_disabled(self):
        factory = Mock(side_effect=[TimeoutError('no READY'), 'verified'])
        with patch.dict('os.environ', {'FIRMWARE_AUTO_FLASH': '0'}), patch('app.firmware.run') as run:
            self.assertEqual(connect_verified(factory, '/dev/mega', 115200, force_flash=True), 'verified')
        run.assert_called_once()
