import json
import logging
import os
import sqlite3
import termios
import threading
import time
from typing import TYPE_CHECKING

import serial

from db import save_session

if TYPE_CHECKING:
    from nextion import NextionDisplay

log = logging.getLogger(__name__)

_NO_DATA_REOPEN_SEC = 30
_WATCHDOG_SEC = 40


def _disable_hupcl(port: str) -> None:
    """Disable HUPCL so the OS does not pulse DTR when the port is opened/closed."""
    try:
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(fd)
        attrs[2] &= ~termios.HUPCL
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        os.close(fd)
    except OSError as e:
        log.warning("Could not disable HUPCL on %s: %s", port, e)


def _resolve_stall(cfg: dict, esp_id: int) -> int:
    return cfg.get("stall_map", {}).get(esp_id, esp_id)


def reader_loop(cfg: dict, conn: sqlite3.Connection, display: "NextionDisplay | None" = None) -> None:
    port = cfg["serial"]["port"]
    baud = cfg["serial"]["baud"]
    timeout = cfg["serial"]["timeout_sec"]

    _disable_hupcl(port)

    while True:
        try:
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = baud
            ser.timeout = timeout
            ser.dtr = False
            ser.rts = False
            ser.open()
            time.sleep(0.5)
            log.info("Serial opened: %s", port)

            last_data = [time.monotonic()]

            def _watchdog(s=ser, ld=last_data):
                while s.isOpen():
                    if time.monotonic() - ld[0] > _WATCHDOG_SEC:
                        log.warning("Watchdog: no data for %ds, closing port to unblock readline", _WATCHDOG_SEC)
                        try:
                            s.close()
                        except Exception:
                            pass
                        return
                    time.sleep(1)

            threading.Thread(target=_watchdog, daemon=True).start()

            try:
                while True:
                    raw = ser.readline()
                    if raw:
                        last_data[0] = time.monotonic()
                        _handle_line(raw, cfg, conn, display)
                    else:
                        if time.monotonic() - last_data[0] >= _NO_DATA_REOPEN_SEC:
                            log.warning("No data for %ds — reopening port", _NO_DATA_REOPEN_SEC)
                            break
            except serial.SerialException as e:
                log.warning("Serial exception (watchdog or device error): %s", e)
            finally:
                try:
                    ser.close()
                except Exception:
                    pass

        except serial.SerialException as e:
            log.warning("Serial error: %s — retry in 5s", e)

        time.sleep(5)


def _handle_line(raw: bytes, cfg: dict, conn: sqlite3.Connection, display: "NextionDisplay | None") -> None:
    try:
        packet = json.loads(raw.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError:
        return
    if not isinstance(packet, dict):
        return

    ptype = packet.get("type")
    stall = _resolve_stall(cfg, packet.get("id", 0))

    if ptype == "session":
        save_session(conn, packet)
        log.debug("Session saved: esp_id=%s stall=%s rfid=%s", packet.get("id"), stall, packet.get("rfid"))

    elif ptype == "snap" and display is not None:
        ts = packet.get("ts", 0)
        ts_str = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else ""
        try:
            display.update_display(
                stall=stall,
                ip=packet.get("ip", ""),
                rfid=packet.get("rfid", ""),
                weight=f"{packet.get('weight', 0) / 1000:.2f}",
                timestamp=ts_str,
                state=packet.get("state", 0) >= 1,
            )
        except Exception as e:
            log.error("update_display error: %s", e, exc_info=True)
