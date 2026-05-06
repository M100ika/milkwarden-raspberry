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
                        _handle_line(raw, conn, display)
        except serial.SerialException as e:
            log.warning("Serial error: %s — retry in 5s", e)
            time.sleep(5)


def _handle_line(raw: bytes, conn: sqlite3.Connection, display: "NextionDisplay | None") -> None:
    try:
        packet = json.loads(raw.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError:
        return

    ptype = packet.get("type")

    if ptype == "session":
        save_session(conn, packet)
        log.debug("Session saved: esp_id=%s rfid=%s", packet.get("id"), packet.get("rfid"))

    elif ptype == "snap" and display is not None:
        display.update_display(
            stall=packet["id"],
            ip=packet.get("ip", ""),
            rfid=packet.get("rfid", ""),
            weight=f"{packet.get('weight', 0) / 1000:.2f} kg",
            state=packet.get("state", 0) >= 1,
        )
