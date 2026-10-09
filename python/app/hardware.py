import os
from collections import deque
import queue
import serial
import threading
import time
import uuid

from app.firmware import FirmwareMismatch


class SerialCommand(str):
    def __new__(cls, text, quiet=False):
        instance = super().__new__(cls, text)
        instance.quiet = quiet
        instance.command_id = None
        instance.origin = "game"
        return instance


class ArduinoController:

    ACK_TIMEOUT = 1.0

    def __init__(
        self,
        port="/dev/cu.usbmodem1101",
        baud=115200,
        ready_timeout=10.0,
        expected_firmware=None,
    ):

        try:
            self.serial = serial.Serial(
                port,
                baud,
                timeout=0.1,
                write_timeout=1.0,
            )

        except Exception as error:
            if getattr(error, 'errno', None) == 2:
                raise RuntimeError(f'NO SERIAL DEVICE FOUND: {port}') from error
            if getattr(error, 'errno', None) == 13:
                raise RuntimeError(f'SERIAL DEVICE PERMISSION DENIED: {port}') from error
            raise

        self.session_id = uuid.uuid4().hex
        self.protocol_version = 1
        self._receipt_lock = threading.Lock()
        self._receipts = {}
        self._next_command_id = 1
        self._current_command = None
        self._command_failure = None
        self._ack_status = None
        self._response_lines = []
        self._last_health = None
        self._health_report = None
        self._health_command_status = None
        self._hardware_outputs = {"moles": {}, "players": {}, "tickets": None}
        self._last_sensor_values = {}
        self.reset_cause = None
        self.event_failure = None
        self._diagnostic_lock = threading.Lock()
        self._recent_errors = deque(maxlen=20)
        self._recent_serial = deque(maxlen=100)
        self._last_serial_at = None
        self._last_sensor_at = {}
        self._sensor_status = {}
        self._rfid_status = "UNKNOWN"
        self._serial_line_count = 0
        self._i2c_timeouts = 0
        self._last_ack = None
        self.firmware_identity = None
        self.event_handler = None
        self.log_raw_accel = os.environ.get("LOG_RAW_ACCEL", "0") == "1"
        self.log_heartbeat = os.environ.get("LOG_HEARTBEAT", "0") == "1"
        self.log_rainbow_commands = os.environ.get("LOG_RAINBOW_COMMANDS", "0") == "1"
        self._quiet_command_ack = False

        # All outgoing commands go through one queue.
        self.command_queue = queue.Queue(maxsize=128)

        # Arduino gameplay events are handled on a separate worker.
        # The serial reader must NEVER run game logic directly because
        # game logic may wait for command ACKs that only the reader can receive.
        self.event_queue = queue.Queue(maxsize=256)
        self._capture_lock = threading.Lock()
        self._sensor_capture = False
        self._captured_samples = queue.Queue(maxsize=256)
        self._captured_ticket_events = queue.Queue()

        # Set by reader thread when Arduino replies
        # OK ... or ERROR ...
        self.command_ack = threading.Event()
        self._ready_event = threading.Event()

        self.running = True
        self.failure_reason = None


        # Read boot diagnostics immediately; do not assume startup takes 2 s.


        # ----------------------------------------------------
        # Reader thread
        # ----------------------------------------------------

        self.reader = threading.Thread(
            target=self._reader_loop,
            daemon=True,
        )

        self.reader.start()
        if not self._ready_event.wait(timeout=ready_timeout):
            self.failure_reason = "Arduino did not report READY during startup"
            self.close()
            raise TimeoutError(self.failure_reason + "; inspect boot output and reset/power-cycle the logic hardware")
        if not self.running:
            self.close()
            raise RuntimeError(self.failure_reason or "Arduino disconnected during startup")


        if expected_firmware is not None and self.firmware_identity != expected_firmware:
            actual = self.firmware_identity or "legacy sketch (no firmware identity)"
            self.close()
            self.reader.join(timeout=1)
            raise FirmwareMismatch(f"running {actual}; expected {expected_firmware}")

        # ----------------------------------------------------
        # Event worker thread
        #
        # Serial reader only receives/parses serial data.
        # Gameplay callbacks run here so ACK reception can continue
        # even while game logic waits for the command queue to drain.
        # ----------------------------------------------------

        self.event_worker = threading.Thread(
            target=self._event_loop,
            daemon=True,
        )

        self.event_worker.start()


        # ----------------------------------------------------
        # Writer thread
        #
        # ONLY this thread writes to the serial port.
        # ----------------------------------------------------

        self.writer = threading.Thread(
            target=self._writer_loop,
            daemon=True,
        )

        self.writer.start()


    # ========================================================
    # PUBLIC SEND
    #
    # This no longer writes directly to serial.
    #
    # It simply places the command into the ordered queue.
    # ========================================================

    def send(
        self,
        command,
        quiet=False,
    ):

        command = command.strip()

        if not command:
            return


        if not self.running:
            raise RuntimeError("Arduino connection is unavailable")
        return self.submit_command(command, quiet=quiet)

    def submit_command(self, command, quiet=False, origin="game"):
        if not self.running:
            raise RuntimeError("Arduino connection is unavailable")
        item = SerialCommand(command, quiet=quiet)
        item.origin = origin
        with self._receipt_lock:
            item.command_id = self._next_command_id
            self._next_command_id += 1
            receipt = {'id': item.command_id, 'session_id': self.session_id, 'command': str(item), 'origin': origin,
                       'status': 'QUEUED', 'queued_at': time.time(), 'response': []}
            try:
                self.command_queue.put_nowait(item)
            except queue.Full:
                raise RuntimeError("Serial command queue is full")
            self._receipts[item.command_id] = receipt
            # Retain recent terminal receipts, never evict pending requests.
            terminal = [key for key, value in self._receipts.items()
                        if value['status'] not in ('QUEUED', 'SENT')]
            for key in terminal[:-128]:
                del self._receipts[key]
        return dict(receipt)

    def command_receipts(self, command_id=None):
        with self._receipt_lock:
            if command_id is not None:
                receipt = self._receipts.get(command_id)
                return dict(receipt) if receipt else None
            return [dict(value) for value in self._receipts.values()]

    def _finish_command(self, command, status, response):
        if not hasattr(self, '_receipt_lock') or getattr(command, 'command_id', None) is None:
            return
        with self._receipt_lock:
            receipt = self._receipts[command.command_id]
            receipt.update(status=status, response=list(response), finished_at=time.time())
        if str(command) == 'HEALTH':
            self._health_command_status = status
        if status == 'ERROR' and command.origin == 'game':
            self._command_failure = f"Command rejected: {command}: {response}"



    # ========================================================
    # WRITER LOOP
    #
    # One command at a time:
    #
    # Python:
    #   SENSORS DISABLE
    #
    # Arduino:
    #   OK SENSORS DISABLED
    #
    # Python:
    #   MOLES ALL UP
    #
    # etc.
    # ========================================================

    def _writer_loop(self):

        while self.running:

            try:

                command = (
                    self.command_queue.get(
                        timeout=0.1
                    )
                )

            except queue.Empty:
                continue


            try:

                # Clear ACK from previous command.
                self.command_ack.clear()
                self._current_command = command
                self._ack_status = None
                self._response_lines = []
                if hasattr(self, '_receipt_lock') and getattr(command, 'command_id', None):
                    with self._receipt_lock:
                        self._receipts[command.command_id]['status'] = 'SENT'


                self._quiet_command_ack = (getattr(command, "quiet", False)
                                           and not getattr(self, "log_rainbow_commands", False))
                if not self._quiet_command_ack:
                    print(f">> {command}")


                message = (
                    (f"@{command.command_id} {command}" if getattr(self, "protocol_version", 1) >= 2
                     else str(command)) + "\n"
                ).encode(
                    "utf-8"
                )


                self.serial.write(
                    message
                )

                self.serial.flush()


                # ------------------------------------------------
                # Wait until Arduino has actually processed
                # this command.
                #
                # The reader thread remains completely independent,
                # so it can receive the ACK while this thread waits.
                # ------------------------------------------------

                acknowledged = (
                    self.command_ack.wait(
                        timeout=self.ACK_TIMEOUT
                    )
                )


                if not acknowledged:

                    self.failure_reason = f"ACK TIMEOUT: {command}"
                    print(f"!! {self.failure_reason}; stopping serial commands for recovery")
                    self._finish_command(command, "TIMEOUT", [self.failure_reason])
                    self.running = False
                    return


                self._finish_command(command, self._ack_status or "OK", self._response_lines)
                self._current_command = None

                # Tiny breathing room after command completion.
                # This is no longer responsible for flow control;
                # the ACK is.
                time.sleep(0.005)


            except serial.SerialException as e:

                print(
                    f"SERIAL WRITE ERROR: {e}"
                )

                self.failure_reason = f"SERIAL WRITE ERROR: {e}"
                self._finish_command(command, "ERROR", [self.failure_reason])
                self.running = False


            finally:

                self.command_queue.task_done()


    # ========================================================
    # READER LOOP
    # ========================================================

    def _reader_loop(self):

        while self.running:

            try:

                line = (
                    self.serial.readline()
                )


            except serial.SerialException as e:
                if not self.running:
                    return  # Expected if close() interrupts an in-flight read.
                print(
                    f"SERIAL READ ERROR: {e}"
                )

                self.failure_reason = f"SERIAL READ ERROR: {e}"
                self.running = False

                return


            if not line:
                continue


            text = line.decode(
                "utf-8",
                errors="ignore",
            ).strip()


            if not text:
                continue
            self._record_serial(text)
            if text == "PROTOCOL 2":
                self.protocol_version = 2
            if text.startswith("FIRMWARE "):
                self.firmware_identity = text
            if text == "READY":
                if self._ready_event.is_set():
                    self.failure_reason = "Unexpected Arduino reset"
                    self._record_error(self.failure_reason)
                    self.running = False
                self._ready_event.set()


            hide_sample = text.startswith("ACCEL ") and not self.log_raw_accel
            hide_heartbeat = text.startswith("HEARTBEAT ") and not getattr(self, "log_heartbeat", False)
            hide_rainbow_ack = (getattr(self, "_quiet_command_ack", False)
                                and text.startswith(("OK LIGHT ", "OK PLAYER_LIGHT ", "ACK ", "OK KEEPALIVE", "OK HEALTH", "OK LEASE", "HEALTH ", "SAMPLE ", "HARDWARE ")))
            if not (hide_sample or hide_heartbeat or hide_rainbow_ack):
                print(f"<< {text}")


            # ------------------------------------------------
            # COMMAND ACKNOWLEDGEMENT
            #
            # Gameplay commands currently return things like:
            #
            # OK SENSORS DISABLED
            # OK MOLES ALL UP
            # OK LIGHT 2 OFF
            #
            # An ERROR also terminates the current command so
            # the queue cannot become stuck forever.
            # ------------------------------------------------

            current = getattr(self, "_current_command", None)
            if current is not None and not text.startswith(("ACCEL ", "HIT ", "HEARTBEAT ")):
                self._response_lines = (self._response_lines + [text])[-32:]
            if text.startswith("ACK "):
                fields = text.split()
                if (len(fields) == 3 and current is not None
                        and fields[1] == str(getattr(current, "command_id", None))
                        and fields[2] in ("OK", "ERROR")):
                    self._ack_status = fields[2]
                    self.command_ack.set()
                    self._quiet_command_ack = False
            elif getattr(self, "protocol_version", 1) < 2 and (
                text.startswith("OK ")
                or
                text.startswith("ERROR ")
            ):

                self._ack_status = "ERROR" if text.startswith("ERROR ") else "OK"
                self.command_ack.set()
                self._quiet_command_ack = False


            # ------------------------------------------------
            # GAME EVENTS
            #
            # Examples:
            #
            # RFID 002
            # RFID_DIAG READY_FOR_NEXT_CARD
            # HIT 3 3 5821
            # ------------------------------------------------

            self._queue_event(text, time.monotonic())


    def _queue_event(self, text, received_at):
        if not text.startswith(("RFID ", "ACCEL ", "HIT ", "TICKET_")):
            return
        with self._capture_lock:
            if self._sensor_capture and text.startswith("TICKET_"):
                self._captured_ticket_events.put_nowait((text, received_at))
            elif self._sensor_capture and text.startswith(("ACCEL ", "HIT ")):
                if self._captured_samples.full():
                    try:
                        self._captured_samples.get_nowait()
                        self._captured_samples.task_done()
                    except queue.Empty:
                        pass
                self._captured_samples.put_nowait((text, received_at))
            elif self.event_handler:
                try:
                    self.event_queue.put_nowait((text, received_at))
                except queue.Full:
                    self.event_failure = "Game event queue is full"
                    self._record_error(self.event_failure)

    def begin_sensor_capture(self):
        with self._capture_lock:
            self._sensor_capture = True
            self.read_captured_samples()

    def end_sensor_capture(self):
        with self._capture_lock:
            self._sensor_capture = False
            self.read_captured_samples()

    def read_captured_samples(self):
        samples = []
        for events in (self._captured_ticket_events, self._captured_samples):
            while True:
                try:
                    samples.append(events.get_nowait())
                    events.task_done()
                except queue.Empty:
                    break
        return samples

    # ========================================================
    # EVENT LOOP
    #
    # Runs gameplay callbacks away from the serial reader.
    # This prevents deadlocks when gameplay waits for queued
    # Arduino commands to receive their ACKs.
    # ========================================================

    def _event_loop(self):

        while self.running:

            try:

                text, received_at = self.event_queue.get(
                    timeout=0.1
                )

            except queue.Empty:
                continue


            try:

                if self.event_handler:

                    self.event_handler(
                        text, received_at=received_at
                    )

            except Exception as e:

                self.event_failure = f"EVENT HANDLER ERROR: {e}"
                self._record_error(self.event_failure)
                print(
                    f"EVENT HANDLER ERROR: {e}"
                )

            finally:

                self.event_queue.task_done()


    # ========================================================
    # OPTIONAL QUEUE DRAIN
    #
    # Useful if we ever need to explicitly wait until every
    # queued hardware command has been processed.
    # ========================================================

    def wait_until_idle(self, timeout=5.0):
        deadline = time.monotonic() + timeout
        with self.command_queue.all_tasks_done:
            while self.command_queue.unfinished_tasks:
                if not self.running:
                    raise RuntimeError("Arduino disconnected while processing commands")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Arduino command queue did not drain")
                self.command_queue.all_tasks_done.wait(min(remaining, 0.1))
        if not self.running:
            raise RuntimeError(self.failure_reason or "Arduino disconnected")
        if getattr(self, "_command_failure", None):
            raise RuntimeError(self._command_failure)


    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        self.running = False
        if hasattr(self, '_receipt_lock'):
            with self._receipt_lock:
                for receipt in self._receipts.values():
                    if receipt['status'] in ('QUEUED', 'SENT'):
                        receipt.update(status='CANCELLED', finished_at=time.time())

        try:

            self.serial.close()

        except Exception:
            pass

    def _record_error(self, message):
        if not hasattr(self, '_diagnostic_lock'):
            return
        with self._diagnostic_lock:
            self._recent_errors.append({'timestamp': time.time(), 'message': message})

    def _record_serial(self, text):
        if not hasattr(self, '_diagnostic_lock'):
            return
        now = time.monotonic()
        parts = text.split()
        with self._diagnostic_lock:
            self._last_serial_at = now
            self._serial_line_count += 1
            self._recent_serial.append({"timestamp": time.time(), "line": text})
            if text.startswith(('OK ', 'ERROR ')):
                self._last_ack = text
            if len(parts) == 2 and parts[0] == 'RESET_CAUSE' and parts[1].isdigit():
                self.reset_cause = int(parts[1])
            if len(parts) == 5 and parts[0] == 'SAMPLE':
                try:
                    self._last_sensor_values[int(parts[1])] = {'x': int(parts[2]), 'y': int(parts[3]), 'z': int(parts[4]), 'source': 'health_poll'}
                    self._last_sensor_at[int(parts[1])] = now
                except ValueError:
                    pass
            if parts[:2] == ['HARDWARE', 'MOLE'] and len(parts) == 7:
                try:
                    self._hardware_outputs['moles'][parts[2]] = {'output_pin': int(parts[4]), 'ring_color': int(parts[6])}
                except ValueError:
                    pass
            if parts[:2] == ['HARDWARE', 'PLAYER'] and len(parts) == 5:
                try:
                    self._hardware_outputs['players'][parts[2]] = {'color': int(parts[4])}
                except ValueError:
                    pass
            if parts[:2] == ['HARDWARE', 'TICKETS'] and len(parts) == 10:
                try:
                    self._hardware_outputs['tickets'] = {parts[index].lower(): int(parts[index + 1]) for index in (2, 4, 6, 8)}
                except ValueError:
                    pass
            if text.startswith('HEALTH MCP '):
                fields = text.split()
                if len(fields) == 9 and all(fields[i].isdigit() for i in (2, 4, 6, 8)):
                    self._health_report = {'mcp_ready': fields[2] == '1', 'sensor_mask': int(fields[4]),
                                           'rfid_ready': fields[6] == '1', 'lease_enabled': fields[8] == '1'}
                    self._last_health = now
            if text == 'I2C_TIMEOUT':
                self._i2c_timeouts += 1
            if text.startswith(('ERROR ', 'I2C_TIMEOUT', 'SENSOR MISSING', 'TICKET_ERROR')) or 'RFID_DIAG ERROR' in text:
                self._recent_errors.append({'timestamp': time.time(), 'message': text})
            if len(parts) >= 3 and parts[0] == 'SENSOR' and parts[1] in ('OK', 'MISSING') and parts[2].isdigit():
                self._sensor_status[int(parts[2])] = parts[1]
            if len(parts) >= 2 and parts[0] in ('ACCEL', 'HIT') and parts[1].isdigit():
                self._last_sensor_at[int(parts[1])] = now
                try:
                    if parts[0] == 'ACCEL' and len(parts) == 6:
                        self._last_sensor_values[int(parts[1])] = {'x': int(parts[3]), 'y': int(parts[4]), 'z': int(parts[5]), 'source': 'stream'}
                    elif parts[0] == 'HIT' and len(parts) == 4:
                        self._last_sensor_values[int(parts[1])] = {'strength': int(parts[3]), 'source': 'hit'}
                except ValueError:
                    pass
            if text == 'RFID_DIAG READER_READY':
                self._rfid_status = 'READY'
            elif 'RFID_DIAG ERROR READER_NOT_RESPONDING' in text:
                self._rfid_status = 'NOT_RESPONDING'

    def get_diagnostics(self):
        now = time.monotonic()
        with self._diagnostic_lock:
            return {
                'connected': self.running,
                'session_id': self.session_id,
                'protocol': self.protocol_version,
                'reset_cause': self.reset_cause,
                'output_pin_and_led_buffer_state': self._hardware_outputs,
                'hardware_health': self._health_report,
                'health_command_status': self._health_command_status,
                'health_age_seconds': round(now - self._last_health, 2) if self._last_health else None,
                'event_failure': self.event_failure,
                'port': self.serial.port,
                'baud': self.serial.baudrate,
                'failure_reason': self.failure_reason,
                'last_received_age_seconds': (round(now - self._last_serial_at, 2)
                                              if self._last_serial_at is not None else None),
                'lines_received': self._serial_line_count,
                'last_ack': self._last_ack,
                'i2c_timeout_count': self._i2c_timeouts,
                'rfid_status_at_last_report': self._rfid_status,
                'sensors': {str(mole): {'startup_status': self._sensor_status.get(mole, 'UNKNOWN'),
                            'last_values': self._last_sensor_values.get(mole),
                            'last_sample_age_seconds': (round(now - self._last_sensor_at[mole], 2)
                                                        if mole in self._last_sensor_at else None)}
                            for mole in range(5)},
                'command_queue_depth': self.command_queue.qsize(),
                'pending_commands': self.command_queue.unfinished_tasks,
                'event_queue_depth': self.event_queue.qsize(),
                'reader_alive': self.reader.is_alive(),
                'writer_alive': self.writer.is_alive(),
                'event_worker_alive': self.event_worker.is_alive(),
                'recent_errors': list(self._recent_errors),
                'recent_serial_lines': list(self._recent_serial),
            }
