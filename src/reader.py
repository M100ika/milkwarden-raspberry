import json
import logging
import sqlite3
import time
from typing import TYPE_CHECKING

import serial

from db import save_session

if TYPE_CHECKING:
    from nextion import NextionDisplay

log = logging.getLogger(__name__)


def _resolve_stall(cfg: dict, esp_id: int) -> int:
    return cfg.get("stall_map", {}).get(esp_id, esp_id)


def reader_loop(cfg: dict, conn: sqlite3.Connection, display: "NextionDisplay | None" = None) -> None:
    port = cfg["serial"]["port"]
    baud = cfg["serial"]["baud"]
    timeout = cfg["serial"]["timeout_sec"]

    while True:
        try:
            with serial.Serial(port, baud, timeout=timeout) as ser:
                log.info("Serial opened: %s", port)
                while True:
                    raw = ser.readline()
                    if raw:
                        _handle_line(raw, cfg, conn, display)
        except serial.SerialException as e:
            log.warning("Serial error: %s — retry in 5s", e)
            time.sleep(5)


def _handle_line(raw: bytes, cfg: dict, conn: sqlite3.Connection, display: "NextionDisplay | None") -> None:
    try:
        packet = json.loads(raw.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError:
        return

    ptype = packet.get("type")
    stall = _resolve_stall(cfg, packet.get("id", 0))

    if ptype == "session":
        save_session(conn, packet)
        log.debug("Session saved: esp_id=%s stall=%s rfid=%s", packet.get("id"), stall, packet.get("rfid"))

    elif ptype == "snap" and display is not None:
        ts = packet.get("ts", 0)
        ts_str = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else ""
        display.update_display(
            stall=stall,
            ip=packet.get("ip", ""),
            rfid=packet.get("rfid", ""),
            weight=f"{packet.get('weight', 0) / 1000:.2f}",
            timestamp=ts_str,
            state=packet.get("state", 0) >= 1,
        )
