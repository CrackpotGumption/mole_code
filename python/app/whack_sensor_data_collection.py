#!/usr/bin/env python3
import time
import serial

PORT = "/dev/cu.usbmodem101"
BAUD = 115200

# Logical mole -> mux channel, for reference in the output.
MUX_CHANNEL = {0: 1, 1: 0, 2: 2, 3: 4, 4: 7}

def send(ser, command):
    print(f"> {command}")
    ser.write((command + "\n").encode("utf-8"))
    ser.flush()

def parse_accel(line):
    # Arduino format:
    # ACCEL <mole> <mux_channel> <x> <y> <z>
    parts = line.split()
    if len(parts) != 6 or parts[0] != "ACCEL":
        return None
    try:
        return tuple(map(int, parts[1:]))  # mole, channel, x, y, z
    except ValueError:
        return None

def main():
    ser = serial.Serial(PORT, BAUD, timeout=0.05)
    time.sleep(2.0)
    ser.reset_input_buffer()

    print("\n=== WHACK SENSOR DATA COLLECTION ===")
    print("Raising all five moles.")
    print("Bop each mole several times. Ctrl+C when finished.\n")

    send(ser, "SENSORS DISABLE")
    send(ser, "MOLES ALL UP")
    time.sleep(1.5)  # let pneumatic motion settle
    ser.reset_input_buffer()
    send(ser, "SENSORS ENABLE")

    print("\nAll moles UP. Recording accelerometers...\n")

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

            # Keep this intentionally raw: every sample from every sensor.
            # This lets us inspect the initial Z impulse, rebound, and ringing.
            print(
                f"ACCEL mole={mole} ch={channel} "
                f"X={x:7d} Y={y:7d} Z={z:7d}"
            )

    except KeyboardInterrupt:
        print("\n\nStopping data collection...")
    finally:
        # Leave the machine in a safe/resting state.
        try:
            send(ser, "SENSORS DISABLE")
            send(ser, "MOLES ALL DOWN")
            time.sleep(0.5)
        finally:
            ser.close()

        print("Moles DOWN. Serial closed.")

if __name__ == "__main__":
    main()
