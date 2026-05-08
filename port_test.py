"""
Auto-detect the master ESP32 serial port and verify JSON packets.
Usage:
  python3 port_test.py               — auto scan
  python3 port_test.py --raw         — dump raw bytes from all ports
  python3 port_test.py --port /dev/ttyUSB0 --baud 115200
"""
import argparse
import glob
import json
import sys
import time

import serial

BAUDS = [115200, 921600, 460800, 230400, 74880, 57600, 38400, 19200, 9600]


def candidates() -> list[str]:
    ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    return sorted(ports)


def read_lines(port: str, baud: int, timeout: float, n: int = 15) -> list[str]:
    try:
        with serial.Serial(port, baud, timeout=timeout) as s:
            time.sleep(0.2)
            s.reset_input_buffer()
            result = []
            deadline = time.time() + timeout * 2
            while len(result) < n and time.time() < deadline:
                raw = s.readline()
                if raw:
                    result.append(raw.decode("utf-8", errors="replace").strip())
            return result
    except serial.SerialException as e:
        print(f"    [err] {e}")
        return []


def is_milkwarden(lines: list[str]) -> bool:
    for line in lines:
        try:
            if json.loads(line).get("type") in ("snap", "session"):
                return True
        except json.JSONDecodeError:
            pass
    return False


def raw_mode(port: str, baud: int) -> None:
    print(f"RAW dump  {port} @ {baud}  (Ctrl+C to stop)\n")
    try:
        with serial.Serial(port, baud, timeout=1) as s:
            s.reset_input_buffer()
            while True:
                raw = s.readline()
                if raw:
                    text = raw.decode("utf-8", errors="replace").strip()
                    print(f"  {text}")
    except serial.SerialException as e:
        print(f"Error: {e}")
    except KeyboardInterrupt:
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port",    default="",    help="specific port to use")
    ap.add_argument("--baud",    type=int, default=0, help="baud rate (0=auto)")
    ap.add_argument("--timeout", type=float, default=4.0)
    ap.add_argument("--raw",     action="store_true", help="dump all bytes, skip detection")
    args = ap.parse_args()

    ports = [args.port] if args.port else candidates()
    if not ports:
        print("No serial ports found (/dev/ttyUSB*, /dev/ttyACM*)")
        print("Run: ls /dev/ttyUSB* /dev/ttyACM*")
        sys.exit(1)

    bauds = [args.baud] if args.baud else BAUDS

    if args.raw:
        port = ports[0]
        baud = bauds[0]
        raw_mode(port, baud)
        return

    print(f"Scanning {ports} at bauds {bauds} ...\n")

    for port in ports:
        for baud in bauds:
            print(f"  {port} @ {baud} ... ", end="", flush=True)
            lines = read_lines(port, baud, args.timeout)
            if not lines:
                print("silent")
                continue
            print(f"{len(lines)} line(s) received:")
            for ln in lines[:8]:
                print(f"    {repr(ln)}")
            if is_milkwarden(lines):
                print(f"\n✓  Milkwarden master: {port} @ {baud}")
                print(f"   config/edge.yaml:")
                print(f"     serial:")
                print(f"       port: \"{port}\"")
                print(f"       baud: {baud}")
                sys.exit(0)
            else:
                print(f"    ^ данные есть, но JSON типа snap/session не найден")

    print("\nNo Milkwarden packets detected.")
    print("Hint: попробуй  python3 port_test.py --raw  чтобы увидеть сырые байты")
    sys.exit(1)


if __name__ == "__main__":
    main()
