import os
import sys
import threading
import time

from app.hardware import ArduinoController
from app.mole_game import MoleGame
from app.status_service import StatusService


# ============================================================
# CONFIGURATION
# ============================================================

ARDUINO_PORT = os.environ.get(
    "ARDUINO_PORT",
    "/dev/cu.usbmodem101",
)

ARDUINO_BAUD = 115200

STATUS_PORT = int(
    os.environ.get(
        "STATUS_PORT",
        "8080",
    )
)


# ============================================================
# HARDWARE
# ============================================================

print()
print("==============================")
print("WHAC GAME CONTROLLER")
print("==============================")
print()
print(
    f"Arduino port: {ARDUINO_PORT}"
)
print(
    f"Arduino baud: {ARDUINO_BAUD}"
)
print(
    f"Status port: {STATUS_PORT}"
)
print()


arduino = ArduinoController(
    port=ARDUINO_PORT,
    baud=ARDUINO_BAUD,
)


# ============================================================
# GAME
# ============================================================

game = MoleGame(
    arduino
)

arduino.event_handler = (
    game.handle_arduino_event
)


# ============================================================
# STATUS SERVICE
# ============================================================

status_service = StatusService(
    game,
    port=STATUS_PORT,
)

status_service.start()


# ============================================================
# KEYBOARD RFID FALLBACK
#
# Type 1-6 followed by Enter to simulate RFID 001-006.
# This calls the same game RFID handler used after a real card read.
# ============================================================

def keyboard_rfid_loop():

    while True:

        try:
            key = sys.stdin.readline()

        except Exception as e:
            print(f"KEYBOARD INPUT ERROR: {e}")
            return

        if key == "":
            return

        key = key.strip()

        if key in ("1", "2", "3", "4", "5", "6"):
            card_id = f"00{key}"
            print(f"KEYBOARD RFID: {card_id}")
            game.handle_rfid(card_id)


keyboard_thread = threading.Thread(
    target=keyboard_rfid_loop,
    daemon=True,
)

keyboard_thread.start()


# ============================================================
# OPTIONAL STARTUP SEQUENCE
#
# Intentionally disabled.
# Uncomment if you want the pneumatic/light startup test.
# ============================================================

# game.startup_sequence()


# ============================================================
# MAIN LOOP
# ============================================================

try:

    while True:
        time.sleep(0.1)


except KeyboardInterrupt:

    print()
    print("Shutting down...")


    arduino.send(
        "SENSORS DISABLE"
    )

    arduino.send(
        "MOLES ALL DOWN"
    )

    arduino.send(
        "LIGHTS OFF"
    )