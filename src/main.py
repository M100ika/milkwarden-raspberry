import logging
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from apscheduler.schedulers.background import BackgroundScheduler

import config as cfg_loader
import db
from nextion import NextionDisplay
from reader import reader_loop
from sync import sync_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def main() -> None:
    cfg = cfg_loader.load()
    conn = db.init_db()

    nx_cfg = cfg.get("nextion", {})
    display: NextionDisplay | None = None
    if nx_cfg.get("enabled", False):
        display = NextionDisplay(
            port=nx_cfg["port"],
            baud=nx_cfg.get("baud", 9600),
            timeout=nx_cfg.get("timeout_sec", 1.0),
        )
        if not display.connect():
            log.warning("Nextion display unavailable — snap forwarding disabled")
            display = None
        else:
            log.info("Nextion display connected: %s", nx_cfg["port"])

    checks_per_day: int = cfg.get("sync", {}).get("checks_per_day", 5)
    interval_hours = 24 / checks_per_day

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        sync_job,
        "interval",
        hours=interval_hours,
        args=[cfg, conn],
        id="sync",
    )
    scheduler.start()
    log.info("Sync scheduler started: every %.1fh", interval_hours)

    reader_thread = threading.Thread(
        target=reader_loop,
        args=[cfg, conn, display],
        daemon=True,
        name="reader",
    )
    reader_thread.start()
    log.info("Reader thread started")

    try:
        reader_thread.join()
    except KeyboardInterrupt:
        log.info("Shutting down")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
