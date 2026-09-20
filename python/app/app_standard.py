#!/usr/bin/env python3
"""
app_standard.py

Simple 45-second standard Whack-a-Mole game for the existing Arduino controller.

Behavior:
- Disables sensor reporting while preparing.
- Lowers all moles and turns all mole lights off.
- 3-second countdown.
- Runs for 45 seconds.
- Multiple random moles can be active simultaneously.
- Starts with up to 2, ramps to 3, then up to 4 near the end.
- Active moles are raised and lit.
- A valid HIT on any active mole scores 1 point and drops it immediately.
- Unhit moles drop after 1.5 seconds.
- Spawn timing has slight random jitter so the rhythm stays unpredictable.
- At game end, all moles drop and lights turn off.
- Prints final score.

Arduino protocol expected:
  SENSORS ENABLE / DISABLE
  MOLES ALL DOWN
  MOLE <0-4> UP / DOWN
  LIGHT <0-4> R G B
  LIGHT <0-4> OFF

Arduino hit format expected:
  HIT <logical_mole> <mux_channel> <strength>
"""

import argparse
import random
import time
import serial


DEFAULT_PORT = "/dev/cu.usbmodem101"
DEFAULT_BAUD = 115200

GAME_SECONDS = 45.0
MOLE_TIMEOUT = 1.5
BETWEEN_MOLES = 0.08

# Keep the same gameplay-strength preference used in the puzzle game.
GAMEPLAY_HIT_THRESHOLD = 18000

MOLE_COUNT = 5

# Bright white active-mole light.
ACTIVE_COLOR = (255, 255, 255)


def send_command(ser, command):
    print(f"> {command}")
    ser.write((command + "\n").encode("utf-8"))
    ser.flush()


def read_lines(ser):
    lines = []
    while ser.in_waiting:
        raw = ser.readline()
        line = raw.decode("utf-8", errors="replace").strip()
        if line:
            print(f"< {line}")
            lines.append(line)
    return lines


def parse_hit(line):
    # HIT <logical_mole> <mux_channel> <strength>
    parts = line.split()

    if len(parts) != 4 or parts[0] != "HIT":
        return None

    try:
        mole = int(parts[1])
        channel = int(parts[2])
        strength = int(parts[3])
    except ValueError:
        return None

    return mole, channel, strength


def set_mole_active(ser, mole):
    r, g, b = ACTIVE_COLOR
    send_command(ser, f"LIGHT {mole} {r} {g} {b}")
    send_command(ser, f"MOLE {mole} UP")


def set_mole_inactive(ser, mole):
    send_command(ser, f"MOLE {mole} DOWN")
    send_command(ser, f"LIGHT {mole} OFF")


def cleanup(ser):
    send_command(ser, "SENSORS DISABLE")
    send_command(ser, "MOLES ALL DOWN")
    send_command(ser, "LIGHTS OFF")


def main():
    parser = argparse.ArgumentParser(
        description="Run a standard 45-second Whack-a-Mole game."
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
        "--duration",
        type=float,
        default=GAME_SECONDS,
        help=f"Game length in seconds (default: {GAME_SECONDS:g})",
    )
    parser.add_argument(
        "--mole-time",
        type=float,
        default=MOLE_TIMEOUT,
        help=f"Maximum seconds each mole stays up (default: {MOLE_TIMEOUT:g})",
    )
    args = parser.parse_args()

    print(f"Opening {args.port} at {args.baud} baud...")
    ser = serial.Serial(args.port, args.baud, timeout=0.05)

    # Opening the serial port can reset the Mega.
    print("Waiting for Arduino startup...")
    time.sleep(2.5)
    ser.reset_input_buffer()

    score = 0

    try:
        cleanup(ser)
        time.sleep(1.0)
        ser.reset_input_buffer()

        print()
        print("STANDARD WHACK-A-MOLE")
        print(f"Game time: {args.duration:g} seconds")
        print(f"Hit threshold: {GAMEPLAY_HIT_THRESHOLD}")
        print()

        for count in (3, 2, 1):
            print(count)
            time.sleep(1.0)

        print("GO!")
        send_command(ser, "SENSORS ENABLE")

        game_start = time.monotonic()
        game_end = game_start + args.duration

        # Each active mole maps to the time it was raised.
        active = {}
        next_spawn = game_start

        while time.monotonic() < game_end:
            now = time.monotonic()
            elapsed = now - game_start
            remaining = game_end - now

            # Ramp the cabinet up as the round progresses:
            # first 10 sec: up to 2 simultaneously
            # next 20 sec: up to 3
            # final 15 sec: up to 4
            if elapsed < 10:
                max_active = 2
                spawn_delay = 0.55
            elif elapsed < 30:
                max_active = 3
                spawn_delay = 0.40
            else:
                max_active = 4
                spawn_delay = 0.28

            # Drop anything that survived for 1.5 seconds.
            expired = [
                mole for mole, raised_at in active.items()
                if now - raised_at >= args.mole_time
            ]

            for mole in expired:
                print(f"MISS: mole {mole + 1}")
                set_mole_inactive(ser, mole)
                del active[mole]

            # Spawn another mole whenever there is room.
            if now >= next_spawn and len(active) < max_active:
                available = [m for m in range(MOLE_COUNT) if m not in active]

                if available:
                    mole = random.choice(available)
                    set_mole_active(ser, mole)
                    active[mole] = time.monotonic()

                # Small random variation keeps the rhythm from becoming mechanical.
                jitter = random.uniform(-0.08, 0.08)
                next_spawn = now + max(0.12, spawn_delay + jitter)

            # Process every hit currently waiting from the Arduino.
            for line in read_lines(ser):
                hit = parse_hit(line)

                if hit is None:
                    continue

                mole, channel, strength = hit

                if strength < GAMEPLAY_HIT_THRESHOLD:
                    print(
                        f"IGNORED: mole {mole} strength {strength} "
                        f"< {GAMEPLAY_HIT_THRESHOLD}"
                    )
                    continue

                if mole not in active:
                    print(f"IGNORED: mole {mole + 1} is not active")
                    continue

                score += 1
                print(f"HIT: mole {mole + 1}   SCORE: {score}")
                set_mole_inactive(ser, mole)
                del active[mole]

                # A successful hit can make room for another mole almost immediately.
                next_spawn = min(next_spawn, time.monotonic() + BETWEEN_MOLES)

            time.sleep(0.01)

        # Kill every mole still active at the buzzer.
        for mole in list(active):
            set_mole_inactive(ser, mole)
        active.clear()

        print()
        print("TIME!")

    except KeyboardInterrupt:
        print("\nGame stopped.")

    finally:
        try:
            cleanup(ser)
            time.sleep(0.25)
        finally:
            ser.close()

    print()
    print("====================")
    print(f"FINAL SCORE: {score}")
    print("====================")


if __name__ == "__main__":
    main()
