#!/usr/bin/env python3
"""
app_flow_control.py

Flow-control tuning utility for the whack-a-mole cabinet.

Cycles one mole at a time:
    Mole 0 UP   -> wait 5 sec -> DOWN -> wait 5 sec
    Mole 1 UP   -> wait 5 sec -> DOWN -> wait 5 sec
    ...
    Mole 4 UP   -> wait 5 sec -> DOWN -> wait 5 sec
    repeat

Arduino protocol used:
    MOLE <0-4> UP
    MOLE <0-4> DOWN

Stop with Ctrl+C. On exit, all moles are commanded DOWN.
"""

import argparse
import time
import serial


DEFAULT_PORT = "/dev/cu.usbmodem101"
DEFAULT_BAUD = 115200
DEFAULT_INTERVAL = 5.0
MOLE_COUNT = 5


def send_command(ser, command):
    print(f"> {command}")
    ser.write((command + "\n").encode("utf-8"))
    ser.flush()

    # Briefly collect/print Arduino replies without blocking the test.
    deadline = time.monotonic() + 0.35
    while time.monotonic() < deadline:
        if ser.in_waiting:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if line:
                print(f"< {line}")
        else:
            time.sleep(0.01)


def all_down(ser):
    send_command(ser, "MOLES ALL DOWN")


def main():
    parser = argparse.ArgumentParser(
        description="Cycle each mole up/down for pneumatic flow-control adjustment."
    )
    parser.add_argument(
        "--port",
        default=DEFAULT_PORT,
        help=f"Arduino serial port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=DEFAULT_BAUD,
        help=f"Serial baud rate (default: {DEFAULT_BAUD})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"Seconds between UP and DOWN actions (default: {DEFAULT_INTERVAL})",
    )
    args = parser.parse_args()

    print(f"Opening {args.port} at {args.baud} baud...")
    ser = serial.Serial(args.port, args.baud, timeout=0.1)

    # Mega commonly resets when the serial port opens.
    print("Waiting for Arduino startup...")
    time.sleep(2.5)
    ser.reset_input_buffer()

    try:
        send_command(ser, "SENSORS DISABLE")
        all_down(ser)
        time.sleep(1.0)

        print()
        print("FLOW CONTROL TEST RUNNING")
        print(f"Each state is held for {args.interval:g} seconds.")
        print("Ctrl+C to stop; all moles will be lowered.")
        print()

        while True:
            for mole in range(MOLE_COUNT):
                print(f"\n=== MOLE {mole + 1} (Arduino mole {mole}) ===")

                send_command(ser, f"MOLE {mole} UP")
                time.sleep(args.interval)

                send_command(ser, f"MOLE {mole} DOWN")
                time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nStopping flow-control test...")

    finally:
        try:
            all_down(ser)
            time.sleep(0.25)
        finally:
            ser.close()

        print("All moles commanded DOWN. Serial port closed.")


if __name__ == "__main__":
    main()
