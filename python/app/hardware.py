import serial
import threading
import time


class ArduinoController:

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

        self.write_lock = threading.Lock()

        time.sleep(2)

        self.reader = threading.Thread(
            target=self._reader_loop,
            daemon=True,
        )

        self.reader.start()


    def send(self, command):

        command = command.strip()

        if not command:
            return

        message = (
            command + "\n"
        ).encode("utf-8")

        with self.write_lock:

            print(
                f">> {command}"
            )

            self.serial.write(
                message
            )

            self.serial.flush()

            # Pace commands so the Mega's
            # RX buffer doesn't overflow.
            time.sleep(0.025)


    def _reader_loop(self):

        while True:

            try:

                line = self.serial.readline()

            except serial.SerialException as e:

                print(
                    f"SERIAL READ ERROR: {e}"
                )

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


            if self.event_handler:

                try:

                    self.event_handler(
                        text
                    )

                except Exception as e:

                    print(
                        f"EVENT HANDLER ERROR: {e}"
                    )