import time

from app.hardware import ArduinoController
from app.mole_game import MoleGame
from app.status_service import StatusService


arduino = ArduinoController(
    port="/dev/cu.usbmodem1101",
    baud=115200,
)

game = MoleGame(
    arduino
)

arduino.event_handler = (
    game.handle_arduino_event
)


status_service = StatusService(
    game,
    port=8080,
)

status_service.start()


print()
print("==============================")
print("WHAC GAME CONTROLLER")
print("==============================")

# Startup sequence disabled for development.
# game.startup_sequence()


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