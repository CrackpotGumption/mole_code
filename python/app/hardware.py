import os
import queue
import serial
import threading
import time


class SerialCommand(str):
    def __new__(cls, text, quiet=False):
        instance = super().__new__(cls, text)
        instance.quiet = quiet
        return instance


class ArduinoController:

    ACK_TIMEOUT = 1.0

    def __init__(
        self,
        port="/dev/cu.usbmodem1101",
        baud=115200,
        ready_timeout=10.0,
    ):

        self.serial = serial.Serial(
            port,
            baud,
            timeout=0.1,
            write_timeout=1.0,
        )

        self.event_handler = None
        self.log_raw_accel = os.environ.get("LOG_RAW_ACCEL", "0") == "1"
        self.log_heartbeat = os.environ.get("LOG_HEARTBEAT", "0") == "1"
        self.log_rainbow_commands = os.environ.get("LOG_RAINBOW_COMMANDS", "0") == "1"
        self._quiet_command_ack = False

        # All outgoing commands go through one queue.
        self.command_queue = queue.Queue()

        # Arduino gameplay events are handled on a separate worker.
        # The serial reader must NEVER run game logic directly because
        # game logic may wait for command ACKs that only the reader can receive.
        self.event_queue = queue.Queue()
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
        self.command_queue.put(
            SerialCommand(command, quiet=quiet)
        )


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


                self._quiet_command_ack = (getattr(command, "quiet", False)
                                           and not getattr(self, "log_rainbow_commands", False))
                if not self._quiet_command_ack:
                    print(f">> {command}")


                message = (
                    command + "\n"
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
                    self.running = False
                    return


                # Tiny breathing room after command completion.
                # This is no longer responsible for flow control;
                # the ACK is.
                time.sleep(0.005)


            except serial.SerialException as e:

                print(
                    f"SERIAL WRITE ERROR: {e}"
                )

                self.failure_reason = f"SERIAL WRITE ERROR: {e}"
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
            if text == "READY":
                self._ready_event.set()


            hide_sample = text.startswith("ACCEL ") and not self.log_raw_accel
            hide_heartbeat = text.startswith("HEARTBEAT ") and not getattr(self, "log_heartbeat", False)
            hide_rainbow_ack = (getattr(self, "_quiet_command_ack", False)
                                and text.startswith(("OK LIGHT ", "OK PLAYER_LIGHT ")))
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

            if (
                text.startswith("OK ")
                or
                text.startswith("ERROR ")
            ):

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
                self.event_queue.put((text, received_at))

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


    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        self.running = False


        try:

            self.serial.close()

        except Exception:
            pass