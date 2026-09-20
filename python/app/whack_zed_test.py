#!/usr/bin/env python3
import time
import serial

PORT = "/dev/cu.usbmodem101"
BAUD = 115200

# All sensors are expected to sit around -1900 Z at idle.
EXPECTED_IDLE_Z = -1900
STARTUP_IDLE_TOLERANCE = 3000

# Equivalent to roughly 4500 counts of additional negative/downward force
# from the common ~-1900 idle position.
DOWN_Z_THRESHOLD = -6400

# Reporting debounce only. Moles stay up so they can be hit repeatedly.
HIT_COOLDOWN = 0.300

STARTUP_SAMPLE_SECONDS = 1.0
NUM_MOLES = 5

def send(ser, command):
    print(f"> {command}")
    ser.write((command + "\n").encode("utf-8"))
    ser.flush()

def parse_accel(line):
    # ACCEL <mole> <mux_channel> <x> <y> <z>
    parts = line.split()
    if len(parts) != 6 or parts[0] != "ACCEL":
        return None
    try:
        return tuple(map(int, parts[1:]))  # mole, channel, x, y, z
    except ValueError:
        return None

def validate_startup_idle(ser):
    samples = {mole: [] for mole in range(NUM_MOLES)}
    deadline = time.monotonic() + STARTUP_SAMPLE_SECONDS

    print(
        f"\nValidating startup idle Z for {STARTUP_SAMPLE_SECONDS:.1f}s "
        f"(expected {EXPECTED_IDLE_Z}, tolerance +/-{STARTUP_IDLE_TOLERANCE})..."
    )

    while time.monotonic() < deadline:
        raw = ser.readline()
        if not raw:
            continue

        line = raw.decode("utf-8", errors="replace").strip()
        accel = parse_accel(line)
        if accel is None:
            if line:
                print(f"< {line}")
            continue

        mole, channel, x, y, z = accel
        if mole in samples:
            samples[mole].append(z)

    print("\nStartup idle check:")
    all_ok = True

    for mole in range(NUM_MOLES):
        values = samples[mole]

        if not values:
            print(f"  mole {mole}: FAIL - no sensor samples")
            all_ok = False
            continue

        avg_z = round(sum(values) / len(values))
        error = avg_z - EXPECTED_IDLE_Z
        ok = abs(error) <= STARTUP_IDLE_TOLERANCE

        print(
            f"  mole {mole}: avg Z={avg_z:6d} "
            f"({error:+d} from expected) "
            f"{'OK' if ok else 'FAIL'}"
        )

        if not ok:
            all_ok = False

    return all_ok

def main():
    ser = serial.Serial(PORT, BAUD, timeout=0.05)
    time.sleep(2.0)
    ser.reset_input_buffer()

    last_hit = {mole: 0.0 for mole in range(NUM_MOLES)}

    print("\n=== DIRECTIONAL HIT TEST ===")
    print(f"Common expected idle Z: {EXPECTED_IDLE_Z}")
    print(f"Hit threshold: Z <= {DOWN_Z_THRESHOLD}")
    print("No per-mole baselines are used.")
    print("Ctrl+C to finish.\n")

    # Startup validation is deliberately done with all moles DOWN/idle.
    send(ser, "MOLES ALL DOWN")
    time.sleep(0.75)
    ser.reset_input_buffer()

    send(ser, "SENSORS ENABLE")

    if not validate_startup_idle(ser):
        print("\n*** STARTUP SENSOR VALIDATION FAILED ***")
        print("One or more sensors are not within the expected idle range.")
        print("Moles will NOT be raised.")
        send(ser, "SENSORS DISABLE")
        ser.close()
        return

    print("\nStartup sensor validation PASSED.")
    print("Sensors stay live; raising all moles now.")
    print("Moles are hittable immediately during the rise.\n")

    send(ser, "MOLES ALL UP")

    try:
        while True:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            accel = parse_accel(line)
            if accel is None:
                print(f"< {line}")
                continue

            mole, channel, x, y, z = accel
            now = time.monotonic()

            if (
                0 <= mole < NUM_MOLES
                and z <= DOWN_Z_THRESHOLD
                and now - last_hit[mole] >= HIT_COOLDOWN
            ):
                last_hit[mole] = now
                print(
                    f"*** HIT *** mole={mole} ch={channel} "
                    f"Z={z} X={x} Y={y}"
                )

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        try:
            send(ser, "SENSORS DISABLE")
            send(ser, "MOLES ALL DOWN")
            time.sleep(0.5)
        finally:
            ser.close()

        print("Moles DOWN. Serial closed.")

if __name__ == "__main__":
    main()
