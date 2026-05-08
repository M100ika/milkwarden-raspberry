"""
Auto-detect the master ESP32 serial port and verify JSON packets.
Usage: python3 port_test.py [--baud 115200] [--timeout 5]
"""
import argparse
import glob
import json
import sys
import time

import serial

BAUDS = [115200, 9600, 57600, 38400]


def candidates() -> list[str]:
    ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    return sorted(ports)


def try_port(port: str, baud: int, timeout: float, lines: int = 10) -> list[str]:
    try:
        with serial.Serial(port, baud, timeout=timeout) as s:
            time.sleep(0.2)
            s.reset_input_buffer()
            found = []
            deadline = time.time() + timeout * 2
            while len(found) < lines and time.time() < deadline:
                raw = s.readline()
                if raw:
                    found.append(raw.decode("utf-8", errors="replace").strip())
            return found
    except serial.SerialException:
        return []


def is_milkwarden(lines: list[str]) -> bool:
    for line in lines:
        try:
            pkt = json.loads(line)
            if pkt.get("type") in ("snap", "session"):
                return True
        except json.JSONDecodeError:
            pass
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baud",    type=int,   default=0,   help="fix baud rate (0 = auto)")
    ap.add_argument("--timeout", type=float, default=4.0, help="read timeout per port (s)")
    args = ap.parse_args()

    ports = candidates()
    if not ports:
        print("No serial ports found (/dev/ttyUSB*, /dev/ttyACM*)")
        sys.exit(1)

    bauds = [args.baud] if args.baud else BAUDS
    print(f"Scanning {ports} at bauds {bauds} ...\n")

    for port in ports:
        for baud in bauds:
            print(f"  {port} @ {baud} ... ", end="", flush=True)
            lines = try_port(port, baud, args.timeout)
            if not lines:
                print("silent")
                continue
            print(f"{len(lines)} line(s)")
            for l in lines[:5]:
                print(f"    {l}")
            if is_milkwarden(lines):
                print(f"\n✓ Milkwarden master found: {port} @ {baud}")
                print(f"  Add to config/edge.yaml:")
                print(f"    serial:")
                print(f"      port: \"{port}\"")
                print(f"      baud: {baud}")
                sys.exit(0)

    print("\nNo Milkwarden packets detected on any port.")
    print("Check: master powered? Serial.begin(115200) in firmware?")
    sys.exit(1)


if __name__ == "__main__":
    main()
