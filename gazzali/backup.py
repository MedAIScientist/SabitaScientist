"""SQLite backups of the PM database: before each deploy and once a week.

Files go to ``<data dir>/backups/<kind>-<UTC timestamp>.db``; only the newest
``keep`` of each kind are kept. deploy/deploy.sh writes the same ``predeploy-*``
files with stdlib-only code, so it works against whatever image is running.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

KEEP = {"predeploy": 3, "weekly": 4}
WEEK_S = 7 * 24 * 3600


def backup_dir(db_path: Path) -> Path:
    return Path(db_path).parent / "backups"


def backup_db(db_path: Path, kind: str, keep: int | None = None) -> Path:
    """Copy the live DB with SQLite's online backup, then prune old copies of this kind."""
    dest_dir = backup_dir(db_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{kind}-{datetime.now(UTC):%Y%m%d-%H%M%S}.db"
    src, out = sqlite3.connect(db_path), sqlite3.connect(dest)
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()
    for old in sorted(dest_dir.glob(f"{kind}-*.db"))[: -(keep or KEEP.get(kind, 3))]:
        old.unlink()
    return dest


def _newest_age_s(db_path: Path, kind: str) -> float | None:
    files = sorted(backup_dir(db_path).glob(f"{kind}-*.db"))
    return time.time() - files[-1].stat().st_mtime if files else None


def start_weekly_backup(db_path: Path, check_every_s: int = 3600) -> threading.Thread:
    """Daemon thread: makes a weekly backup when the newest one is a week old (or missing)."""

    def loop() -> None:
        while True:
            try:
                age = _newest_age_s(db_path, "weekly")
                if age is None or age >= WEEK_S:
                    logger.info("weekly DB backup: %s", backup_db(db_path, "weekly"))
            except (OSError, sqlite3.Error):
                logger.exception("weekly DB backup failed")
            time.sleep(check_every_s)

    t = threading.Thread(target=loop, name="weekly-db-backup", daemon=True)
    t.start()
    return t
