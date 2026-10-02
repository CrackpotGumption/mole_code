import os
import signal
import sys
import threading
import time


def keyboard_rfid_loop(arduino, stopped):
    """Queue keyboard badges through the same worker as physical badges."""
    while not stopped.is_set():
        try:
            key = sys.stdin.readline()
        except Exception as error:
            print(f"KEYBOARD INPUT ERROR: {error}")
            return
        if key == "":
            return
        key = key.strip()
        if key in ("1", "2", "3", "4", "5", "6"):
            card_id = f"00{key}"
            arduino.event_queue.put((f"RFID {card_id}", time.monotonic()))


def main():
    from app.audio_cues import AudioCues
    from app.hardware import ArduinoController
    from app.mole_game import MoleGame
    from app.status_service import StatusService

    port = os.environ.get("ARDUINO_PORT", "/dev/cu.usbmodem101")
    status_port = int(os.environ.get("STATUS_PORT", "8080"))
    stopped = threading.Event()
    previous_handlers = {}
    arduino = game = status_service = audio = None

    def request_shutdown(signum, frame):
        # Serial operations run in finally, never inside the signal handler.
        stopped.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, request_shutdown)

    try:
        print(f"MOLE GAME CONTROLLER | Arduino: {port} at 115200 | Status: {status_port}")
        arduino = ArduinoController(port=port, baud=115200)
        audio = AudioCues()
        game = MoleGame(arduino, state_path=os.environ.get("GAME_STATE_PATH") or None,
                        audio=audio, failure_seconds=os.environ.get("FAILURE_SECONDS", "15"),
                        stop_requested=stopped.is_set)
        game.restore_hardware()
        arduino.event_handler = game.handle_arduino_event
        status_service = StatusService(game, port=status_port)
        status_service.start()
        threading.Thread(target=keyboard_rfid_loop, args=(arduino, stopped), daemon=True).start()

        while not stopped.wait(0.1):
            if game.persistence_error is not None:
                raise RuntimeError(f"Progress could not be saved: {game.persistence_error}")
            if not arduino.running:
                print("Arduino connection lost; exiting so the container can restart.")
                return 1
        return 0
    except Exception as error:
        print(f"CONTROLLER ERROR: {error}", file=sys.stderr)
        return 1
    finally:
        stopped.set()
        if arduino is not None:
            arduino.event_handler = None
            if game is not None and arduino.running:
                try:
                    game.retract_game()
                    arduino.send("PLAYER_LIGHTS OFF")
                    arduino.wait_until_idle(timeout=3.0)
                except Exception as error:
                    print(f"SHUTDOWN ERROR: {error}", file=sys.stderr)
            if status_service is not None:
                status_service.stop()
            arduino.close()
        if audio is not None:
            audio.close()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
