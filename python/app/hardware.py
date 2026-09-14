import queue
import serial
import threading
import time


class ArduinoController:

    ACK_TIMEOUT = 1.0

    def __init__(
        self,
        port="/dev/cu.usbmodem1101",
        baud=115200,
    ):

        self.serial = serial.Serial(
            port,
            baud,
            timeout=0.1,
        )

        self.event_handler = None

        # All outgoing commands go through one queue.
        self.command_queue = queue.Queue()

        # Set by reader thread when Arduino replies
        # OK ... or ERROR ...
        self.command_ack = threading.Event()

        self.running = True


        # Mega resets when serial connection opens.
        time.sleep(2)


        # ----------------------------------------------------
        # Reader thread
        # ----------------------------------------------------

        self.reader = threading.Thread(
            target=self._reader_loop,
            daemon=True,
        )

        self.reader.start()


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
    ):

        command = command.strip()

        if not command:
            return


        self.command_queue.put(
            command
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


                print(
                    f">> {command}"
                )


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

                    print(
                        f"!! ACK TIMEOUT: {command}"
                    )


                # Tiny breathing room after command completion.
                # This is no longer responsible for flow control;
                # the ACK is.
                time.sleep(0.005)


            except serial.SerialException as e:

                print(
                    f"SERIAL WRITE ERROR: {e}"
                )

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

                print(
                    f"SERIAL READ ERROR: {e}"
                )

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


            print(
                f"<< {text}"
            )


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


            # ------------------------------------------------
            # GAME EVENTS
            #
            # Examples:
            #
            # RFID 002
            # RFID_DIAG READY_FOR_NEXT_CARD
            # HIT 3 4 5821
            # ------------------------------------------------

            if self.event_handler:

                try:

                    self.event_handler(
                        text
                    )

                except Exception as e:

                    print(
                        f"EVENT HANDLER ERROR: {e}"
                    )


    # ========================================================
    # OPTIONAL QUEUE DRAIN
    #
    # Useful if we ever need to explicitly wait until every
    # queued hardware command has been processed.
    # ========================================================

    def wait_until_idle(self):

        self.command_queue.join()


    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        self.running = False


        try:

            self.serial.close()

        except Exception:
            pass