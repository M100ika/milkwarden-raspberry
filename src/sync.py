import logging
import socket
import sqlite3

import httpx

from db import delete_synced, get_pending

log = logging.getLogger(__name__)


def wifi_connected() -> bool:
    try:
        socket.setdefaulttimeout(3)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("8.8.8.8", 53))
        return True
    except OSError:
        return False


def sync_job(cfg: dict, conn: sqlite3.Connection) -> None:
    srv = cfg["server"]
    if not srv.get("enabled", False):
        return
    if not wifi_connected():
        log.info("Sync skipped: no WiFi")
        return

    rows = get_pending(conn, limit=srv.get("batch_size", 50))
    if not rows:
        return

    payload = {
        "device": cfg.get("device_id", "milkwarden-edge-01"),
        "sessions": [dict(r) for r in rows],
    }
    try:
        resp = httpx.post(
            srv["url"],
            json=payload,
            timeout=srv.get("timeout_sec", 10),
        )
        if resp.status_code == 200:
            delete_synced(conn, [r["id"] for r in rows])
            log.info("Synced %d sessions", len(rows))
        else:
            log.warning("Sync failed: HTTP %d", resp.status_code)
    except httpx.RequestError as e:
        log.warning("Sync error: %s", e)
