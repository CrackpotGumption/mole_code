import os
import signal
import sys
import threading
import time


def keyboard_rfid_loop(cabinet, stopped):
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
        if key.upper() in ("RFID STATUS", "RFID INIT", "HEARTBEAT ON", "HEARTBEAT OFF"):
            try:
                if callable(getattr(cabinet, "submit", None)):
                    cabinet.serial(key.upper())
                else:
                    cabinet.send(key.upper())
            except (RuntimeError, ValueError) as error:
                print(f"CONSOLE ERROR: {error}")
            continue
        if key.upper().startswith("RFID "):
            key = key[5:].strip()
        if key in ("1", "2", "3", "4", "5", "6"):
            key = f"00{key}"
        if key in ("001", "002", "003", "004", "005", "006"):
            try:
                if callable(getattr(cabinet, "submit", None)):
                    cabinet.submit("badge", {"player": key})
                else:
                    cabinet.event_queue.put((f"RFID {key}", time.monotonic()))
            except (RuntimeError, ValueError) as error:
                print(f"CONSOLE ERROR: {error}")


def main():
    from app.cabinet import Cabinet
    from app.diagnostics import application_info
    from app.hardware import ArduinoController
    from app.status_service import StatusService

    port = os.environ.get("ARDUINO_PORT", "/dev/cu.usbmodem101")
    stopped = threading.Event()
    cabinet = service = None
    previous_handlers = {}
    def request_shutdown(signum, frame):
        stopped.set()
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, request_shutdown)
    try:
        print(f"APPLICATION {application_info()}")
        cabinet = Cabinet(ArduinoController, port, stopped)
        service = StatusService(cabinet, port=int(os.environ.get("STATUS_PORT", "8080")))
        service.start()
        cabinet.start()
        threading.Thread(target=keyboard_rfid_loop, args=(cabinet, stopped), daemon=True).start()
        while not stopped.wait(0.1):
            cabinet.tick()
        return 0
    except Exception as error:
        print(f"CONTROLLER ERROR: {error}", file=sys.stderr)
        return 1
    finally:
        stopped.set()
        if cabinet:
            cabinet.close()
        if service:
            service.stop()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
