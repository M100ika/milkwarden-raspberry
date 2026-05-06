import sqlite3
import time
from pathlib import Path
from typing import Any

_DB_PATH = Path.home() / ".milkwarden" / "milkwarden.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    esp_id       INTEGER NOT NULL,
    rfid_tag     TEXT    NOT NULL DEFAULT '',
    weight_init  REAL    NOT NULL,
    weight_final REAL    NOT NULL,
    t_start      INTEGER NOT NULL,
    t_end        INTEGER NOT NULL,
    end_reason   INTEGER NOT NULL,
    received_at  INTEGER NOT NULL,
    synced       INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_INDEX = "CREATE INDEX IF NOT EXISTS idx_synced ON sessions (synced);"


def init_db(path: Path = _DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE)
    conn.execute(_CREATE_INDEX)
    conn.commit()
    return conn


def save_session(conn: sqlite3.Connection, packet: dict[str, Any]) -> None:
    conn.execute(
        """INSERT INTO sessions
           (esp_id, rfid_tag, weight_init, weight_final,
            t_start, t_end, end_reason, received_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            packet["id"],
            packet.get("rfid", ""),
            packet["w_init"],
            packet["w_final"],
            packet["t_start"],
            packet["t_end"],
            packet["reason"],
            int(time.time()),
        ),
    )
    conn.commit()


def get_pending(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sessions WHERE synced=0 LIMIT ?", (limit,)
    ).fetchall()


def delete_synced(conn: sqlite3.Connection, ids: list[int]) -> None:
    conn.execute(
        f"DELETE FROM sessions WHERE id IN ({','.join('?' * len(ids))})", ids
    )
    conn.commit()
