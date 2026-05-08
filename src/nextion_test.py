"""
Тест Nextion NX4827T043.
Запуск: python src/nextion_test.py [--config config/nextion_test.yaml]
"""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yaml

from nextion import NextionDisplay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

_PASS = "\033[92mPASS\033[0m"
_FAIL = "\033[91mFAIL\033[0m"
_SKIP = "\033[93mSKIP\033[0m"


def _load(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ── тесты ────────────────────────────────────────────────────────────────────

def test_connection(display: NextionDisplay, cfg: dict) -> bool:
    name = "connection"
    if not cfg["tests"][name].get("enabled", True):
        print(f"  {_SKIP} {name}")
        return True

    print(f"  [{name}] bkcmd=3 + get sys.time ...")
    try:
        display.send("bkcmd=3")
        display.send("get sys.time")
        resp = display.read_response(timeout=1.5)
        if resp:
            print(f"    ответ: {display.decode_response(resp)}")
            print(f"  {_PASS} {name}")
            return True
        print("    нет ответа от дисплея")
        print(f"  {_FAIL} {name}")
        return False
    except Exception as e:
        print(f"    ошибка: {e}")
        print(f"  {_FAIL} {name}")
        return False


def test_text_display(display: NextionDisplay, cfg: dict) -> bool:
    name = "text_display"
    if not cfg["tests"][name].get("enabled", True):
        print(f"  {_SKIP} {name}")
        return True

    page = cfg["nextion"]["components"].get("page_main", 0)
    print(f"  [{name}] страница {page}, 4 стойки ...")
    try:
        display.set_page(page)
        time.sleep(0.3)
        for n in range(1, 5):
            display.update_display(
                stall=n,
                ip=f"192.168.1.{n}",
                rfid=f"RFID-TEST-{n}",
                weight="0.00",
                state=False,
            )
            time.sleep(0.05)
        print(f"  {_PASS} {name}")
        return True
    except Exception as e:
        print(f"    ошибка: {e}")
        print(f"  {_FAIL} {name}")
        return False


def test_simulate_session(display: NextionDisplay, cfg: dict) -> bool:
    """IDLE → COW_PRESENT → MILKING (нарастающий вес) → IDLE."""
    name = "simulate_session"
    tc = cfg["tests"][name]
    if not tc.get("enabled", True):
        print(f"  {_SKIP} {name}")
        return True

    stall_id = int(tc.get("stall_id", 1))
    rfid     = str(tc.get("rfid", "E20068151234ABCD"))
    w_start  = float(tc.get("weight_start_g", 0.0))
    w_end    = float(tc.get("weight_end_g", 14500.0))
    duration = float(tc.get("duration_sec", 20))
    interval = float(tc.get("snap_interval_ms", 500)) / 1000.0
    ip       = str(tc.get("ip", "192.168.1.1"))

    print(f"  [{name}] стойка {stall_id}, {duration}s, шаг {interval*1000:.0f}ms")
    try:
        print("    IDLE ...")
        display.update_display(stall=stall_id, ip=ip, rfid="", weight="0.00", state=False)
        time.sleep(1.0)

        print("    COW_PRESENT ...")
        display.update_display(stall=stall_id, ip=ip, rfid=rfid, weight=f"{w_start/1000:.2f}", state=True)
        time.sleep(1.0)

        steps = max(1, int(duration / interval))
        print(f"    MILKING ({steps} шагов) ...")
        for i in range(steps + 1):
            w = w_start + (w_end - w_start) * (i / steps)
            display.update_display(stall=stall_id, ip=ip, rfid=rfid, weight=f"{w/1000:.2f}", state=True)
            time.sleep(interval)

        print("    IDLE (сессия завершена)")
        display.update_display(stall=stall_id, ip=ip, rfid="", weight="0.00", state=False)

        print(f"  {_PASS} {name}")
        return True
    except Exception as e:
        print(f"    ошибка: {e}")
        print(f"  {_FAIL} {name}")
        return False


def test_simulate_all_stalls(display: NextionDisplay, cfg: dict) -> bool:
    """4 стойки с разными фазами дойки, однопоточно."""
    name = "simulate_all_stalls"
    tc = cfg["tests"][name]
    if not tc.get("enabled", False):
        print(f"  {_SKIP} {name}")
        return True

    interval = float(tc.get("snap_interval_ms", 500)) / 1000.0
    duration = float(tc.get("duration_sec", 30))

    stalls = [
        {"id": 1, "ip": "192.168.1.1", "rfid": "AABB112200000001", "active": True,  "phase": 0.00},
        {"id": 2, "ip": "192.168.1.2", "rfid": "CCDD334400000002", "active": True,  "phase": 0.25},
        {"id": 3, "ip": "192.168.1.3", "rfid": "",                  "active": False, "phase": 0.50},
        {"id": 4, "ip": "192.168.1.4", "rfid": "EEFF556600000004", "active": True,  "phase": 0.75},
    ]
    w_max = 14500.0
    steps = max(1, int(duration / interval))

    print(f"  [{name}] {duration}s, {interval*1000:.0f}ms интервал ...")
    try:
        for step in range(steps):
            elapsed = step * interval
            for s in stalls:
                t = (elapsed + s["phase"] * duration) % duration
                w = w_max * (t / duration) if s["active"] else 0.0
                display.update_display(
                    stall=s["id"],
                    ip=s["ip"],
                    rfid=s["rfid"],
                    weight=f"{w/1000:.2f}",
                    state=s["active"],
                )
            time.sleep(interval)

        print(f"  {_PASS} {name}")
        return True
    except Exception as e:
        print(f"    ошибка: {e}")
        print(f"  {_FAIL} {name}")
        return False


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Nextion NX4827T043 test")
    parser.add_argument(
        "--config",
        default="config/nextion_test.yaml",
        help="Путь к конфигу (default: config/nextion_test.yaml)",
    )
    args = parser.parse_args()

    cfg = _load(args.config)

    if not cfg.get("tests", {}).get("enabled", True):
        print("Тесты отключены (tests.enabled: false)")
        sys.exit(0)

    nx = cfg["nextion"]
    display = NextionDisplay(
        port=nx["port"],
        baud=nx.get("baud", 9600),
        timeout=nx.get("timeout_sec", 1.0),
    )

    print(f"\nNextion Test  {nx['port']} @ {nx.get('baud', 9600)} baud")
    print("=" * 52)

    if not display.connect():
        print(f"{_FAIL}  не удалось открыть {nx['port']}")
        sys.exit(1)

    results: list[bool] = []
    try:
        results.append(test_connection(display, cfg))
        results.append(test_text_display(display, cfg))
        results.append(test_simulate_session(display, cfg))
        results.append(test_simulate_all_stalls(display, cfg))
    finally:
        display.disconnect()

    print("=" * 52)
    passed = sum(results)
    total  = len(results)
    status = _PASS if passed == total else _FAIL
    print(f"Итог: {status}  {passed}/{total} тестов пройдено")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
