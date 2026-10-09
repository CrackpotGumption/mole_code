import queue
import time
import unittest
from unittest.mock import patch

from test_sensor_capture import ArduinoController


class Port:
    port, baudrate = '/dev/test', 115200
    def __init__(self, acknowledge=True):
        self.input = queue.Queue()
        self.output = []
        self.acknowledge = acknowledge
        for line in ('PROTOCOL 2', 'READY'):
            self.input.put((line + '\n').encode())
    def readline(self):
        try:
            return self.input.get(timeout=0.01)
        except queue.Empty:
            return b''
    def write(self, data):
        self.output.append(data)
        identity, command = data.decode().strip().split(' ', 1)
        if command == 'BAD':
            self.input.put(b'ERROR UNKNOWN COMMAND BAD\n')
            state = 'ERROR'
        else:
            self.input.put(b'OK DIAGNOSTIC\n')
            state = 'OK'
        if self.acknowledge:
            self.input.put(b'ACK 9999 OK\n')  # unrelated command cannot release writer
            self.input.put(f'ACK {identity[1:]} {state}\n'.encode())
    def flush(self):
        pass
    def close(self):
        pass


class CommandReceiptTests(unittest.TestCase):
    def connect(self, acknowledge=True):
        port = Port(acknowledge)
        module = ArduinoController.__init__.__globals__['serial']
        with patch.object(module, 'Serial', return_value=port, create=True):
            controller = ArduinoController(ready_timeout=0.2)
        controller.ACK_TIMEOUT = 0.05
        self.addCleanup(controller.close)
        return controller, port
    def test_correlated_success_and_error_receipts(self):
        controller, port = self.connect()
        success = controller.submit_command('PING', origin='admin')
        error = controller.submit_command('BAD', origin='admin')
        controller.wait_until_idle()
        self.assertEqual(controller.command_receipts(success['id'])['status'], 'OK')
        self.assertEqual(controller.command_receipts(error['id'])['status'], 'ERROR')
        self.assertEqual(port.output[0], b'@1 PING\n')
        self.assertTrue(controller.running)
    def test_game_command_rejection_propagates_to_waiter(self):
        controller, _ = self.connect()
        receipt = controller.send('BAD')
        with self.assertRaisesRegex(RuntimeError, 'Command rejected'):
            controller.wait_until_idle()
        self.assertEqual(controller.command_receipts(receipt['id'])['status'], 'ERROR')
    def test_untracked_ok_does_not_ack_protocol_two_command(self):
        controller, _ = self.connect(acknowledge=False)
        receipt = controller.send('PING')
        with self.assertRaises(RuntimeError):
            controller.wait_until_idle()
        self.assertEqual(controller.command_receipts(receipt['id'])['status'], 'TIMEOUT')
        self.assertFalse(controller.running)
    def test_second_ready_is_reported_as_reset(self):
        controller, port = self.connect()
        port.input.put(b'READY\n')
        deadline = time.monotonic() + 0.5
        while controller.running and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertFalse(controller.running)
        self.assertEqual(controller.failure_reason, 'Unexpected Arduino reset')
