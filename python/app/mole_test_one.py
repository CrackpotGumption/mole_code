#!/usr/bin/env python3
import random
import time
import serial

PORT = "/dev/cu.usbmodem101"
BAUD = 115200

NUM_MOLES = 5
TARGET_UP = 1

# Current directional hit rule.
HIT_Z_THRESHOLD = -9000

# Startup sanity check only; not used for gameplay hit calculations.
EXPECTED_IDLE_Z = -1900
STARTUP_IDLE_TOLERANCE = 3000
STARTUP_SAMPLE_SECONDS = 1.0

# Debug/watchdog output.
STATUS_INTERVAL = 1.0
STREAM_STALL_WARNING = 0.5

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
    samples = {m: [] for m in range(NUM_MOLES)}
    deadline = time.monotonic() + STARTUP_SAMPLE_SECONDS

    print(
        f"\nValidating idle sensors for {STARTUP_SAMPLE_SECONDS:.1f}s "
        f"(expected Z about {EXPECTED_IDLE_Z}, +/-{STARTUP_IDLE_TOLERANCE})..."
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

    ok = True
    for mole in range(NUM_MOLES):
        vals = samples[mole]
        if not vals:
            print(f"  mole {mole}: FAIL - no samples")
            ok = False
            continue

        avg = round(sum(vals) / len(vals))
        good = abs(avg - EXPECTED_IDLE_Z) <= STARTUP_IDLE_TOLERANCE
        print(f"  mole {mole}: avg Z={avg:6d}  {'OK' if good else 'FAIL'}")
        ok &= good

    return ok

def choose_replacement(active, previous_hit=None):
    candidates = [m for m in range(NUM_MOLES) if m not in active]

    # When possible, don't immediately re-raise the mole that was just hit.
    # With 5 total / 3 active there will normally be another choice.
    alternatives = [m for m in candidates if m != previous_hit]
    if alternatives:
        candidates = alternatives

    return random.choice(candidates)

def raise_mole(ser, mole, active):
    # Mark active BEFORE issuing UP: it is hittable from the instant
    # the pneumatic rise begins.
    active.add(mole)
    send(ser, f"LIGHT {mole} 255 255 255")
    send(ser, f"MOLE {mole} UP")
    print(f"+++ ACTIVE {mole}  ({len(active)}/{TARGET_UP})")

def lower_hit_mole(ser, mole, active, z):
    # Critical ordering: make it unhittable BEFORE commanding DOWN.
    active.discard(mole)
    print(f"\n*** HIT mole={mole} Z={z} ***")
    send(ser, f"LIGHT {mole} 0 0 0")
    send(ser, f"MOLE {mole} DOWN")

def fill_to_three(ser, active, previous_hit=None):
    first = True
    while len(active) < TARGET_UP:
        mole = choose_replacement(
            active,
            previous_hit if first else None
        )
        raise_mole(ser, mole, active)
        first = False

def main():
    ser = serial.Serial(PORT, BAUD, timeout=0.02)
    time.sleep(2.0)
    ser.reset_input_buffer()

    active = set()
    score = 0

    # Sensor-stream diagnostics.
    sample_count = 0
    samples_since_status = 0
    last_accel_time = time.monotonic()
    last_status_time = time.monotonic()
    stall_reported = False

    print("\n=== ONE-UP DIRECTIONAL WHACK TEST ===")
    print("Exactly one mole stays active at a time.")
    print(f"Hit rule: active mole with Z <= {HIT_Z_THRESHOLD}.")
    print("No timeout: moles retract ONLY when hit.")
    print("A mole is hittable immediately when UP is commanded.")
    print("Ctrl+C to stop.")
    print(
        f"Debug: status every {STATUS_INTERVAL:.1f}s; "
        f"stall warning after {STREAM_STALL_WARNING:.1f}s without ACCEL.\n"
    )

    send(ser, "SENSORS DISABLE")
    send(ser, "MOLES ALL DOWN")
    send(ser, "LIGHTS OFF")
    time.sleep(0.75)
    ser.reset_input_buffer()

    send(ser, "SENSORS ENABLE")

    if not validate_startup_idle(ser):
        print("\n*** STARTUP SENSOR VALIDATION FAILED ***")
        print("Moles will not be raised.")
        send(ser, "SENSORS DISABLE")
        ser.close()
        return

    print("\nSensor validation PASSED.\n")

    # Start with one random target.
    fill_to_three(ser, active)

    try:
        while True:
            raw = ser.readline()
            now = time.monotonic()

            # Even when readline times out, keep the watchdog alive.
            if not raw:
                if now - last_accel_time >= STREAM_STALL_WARNING and not stall_reported:
                    print(
                        f"\n*** SENSOR STREAM STALLED - "
                        f"no ACCEL for {now - last_accel_time:.3f}s ***"
                    )
                    stall_reported = True

                if now - last_status_time >= STATUS_INTERVAL:
                    elapsed = now - last_status_time
                    rate = samples_since_status / elapsed if elapsed > 0 else 0.0
                    active_text = ",".join(map(str, sorted(active))) if active else "NONE"
                    print(
                        f"[STATUS] {rate:.1f} samples/sec | "
                        f"active={active_text} | score={score} | "
                        f"last_accel={now - last_accel_time:.3f}s ago | "
                        f"total={sample_count}"
                    )
                    samples_since_status = 0
                    last_status_time = now
                continue

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            accel = parse_accel(line)

            if accel is None:
                # Keep ACKs / diagnostics visible.
                print(f"< {line}")
                continue

            mole, channel, x, y, z = accel

            # Any valid ACCEL packet proves the Arduino sensor stream is alive.
            now = time.monotonic()
            last_accel_time = now
            sample_count += 1
            samples_since_status += 1

            if stall_reported:
                print("*** SENSOR STREAM RESUMED ***")
                stall_reported = False

            if now - last_status_time >= STATUS_INTERVAL:
                elapsed = now - last_status_time
                rate = samples_since_status / elapsed if elapsed > 0 else 0.0
                active_text = ",".join(map(str, sorted(active))) if active else "NONE"
                print(
                    f"[STATUS] {rate:.1f} samples/sec | "
                    f"active={active_text} | score={score} | "
                    f"last_accel={now - last_accel_time:.3f}s ago | "
                    f"total={sample_count}"
                )
                samples_since_status = 0
                last_status_time = now

            # Inactive sensors are irrelevant, regardless of how violent
            # their pneumatic DOWN/retraction signal is.
            if mole not in active:
                continue

            if z <= HIT_Z_THRESHOLD:
                lower_hit_mole(ser, mole, active, z)
                score += 1
                print(f"SCORE: {score}")

                # Immediately raise a different mole.
                fill_to_three(ser, active, previous_hit=mole)

    except KeyboardInterrupt:
        print(f"\n\nStopping. Final score: {score}")
    finally:
        try:
            active.clear()
            send(ser, "SENSORS DISABLE")
            send(ser, "LIGHTS OFF")
            send(ser, "MOLES ALL DOWN")
            time.sleep(0.5)
        finally:
            ser.close()

        print("All moles DOWN. Serial closed.")

if __name__ == "__main__":
    main()
