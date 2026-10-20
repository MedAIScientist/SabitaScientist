"""Hear delivery facts from platform-control within seconds, not within the hour.

The firewall opens DMZ -> cluster only, so the cluster can never tell Medai that a cohort was
sealed or that its delivery started — Medai has to ask. It used to ask once an hour (the cron in
integrations/platform-status-sync), and on 2026-10-17 two researchers with readable data watched
"Waiting on delivery" for half an hour because of it.

So this thread HOLDS a question open instead: GET /v1/events?after=<cursor> is answered by
platform-control the moment a fact changes on its side (a seal, a delivery starting), or after
WAIT_SECONDS with "nothing yet". Each answer that moved the cursor runs the same sync the cron
runs (platform_pull.sync_delivery_facts). The answer carries no payload, so a missed or duplicated
wake-up costs one idempotent sync, never a wrong state; the hourly cron stays as the safety net.

One watcher per host: a file lock next to the database, so a second process (another worker, a
REPL) finds it held and stays quiet. Started from `serve()` like the other background workers.
"""

from __future__ import annotations

import fcntl
import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import IO

from . import platform_pull

logger = logging.getLogger(__name__)

WAIT_SECONDS = 25
_BACKOFF_MAX_SECONDS = 60.0

# Held for the life of the process: closing the file would release the singleton lock.
_singleton: IO[str] | None = None


def configured() -> bool:
    if os.environ.get("MEDAI_PLATFORM_WATCH", "1") == "0":
        return False
    return bool(os.environ.get("MEDAI_PLATFORM_CONTROL_URL")
                and os.environ.get("MEDAI_PLATFORM_CONTROL_TOKEN"))


def step(db: Path, cursor: dict | None) -> dict:
    """One held request, and a sync when it says something moved (or when there is no cursor
    yet: the first call catches up on anything that happened while nobody was listening)."""
    after = platform_pull.wait_for_change(cursor, wait_seconds=WAIT_SECONDS)
    if cursor is None or after != cursor:
        with platform_pull.sync_lock(db):
            report = platform_pull.sync_delivery_facts(db, apply=True)
        if report.changed or report.errors:
            logger.info("platform watch: %s", report.summary())
        if report.errors:
            # Not advancing the cursor makes the next request answer at once, so a sync that
            # failed half way is retried (after the loop's backoff) instead of forgotten.
            raise RuntimeError("; ".join(report.errors))
    return after


def _claim(db: Path) -> IO[str] | None:
    handle = open(Path(db).parent / ".platform_watch.lock", "a")  # held for the process's life
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def _make_audible() -> None:
    """Inside serve() nothing configures logging, so INFO lines would be dropped and the watch's
    writes to the system of record would leave no trace in the container log. Give the watch's
    and the sync's loggers their own stderr handler (docker logs keeps it); the audit_log rows are
    the durable record either way. Deliberately NOT gazzali.platform_push: its INFO lines name
    researchers by e-mail on every membership push, and nothing here needs them in the log."""
    for name in ("gazzali.platform_watch", "gazzali.platform_pull"):
        log = logging.getLogger(name)
        if not log.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            log.addHandler(handler)
            log.setLevel(logging.INFO)
            log.propagate = False


def run_forever(db: Path, *, sleep: Callable[[float], None] = time.sleep,
                keep_going: Callable[[], bool] = lambda: True) -> None:
    """The watch loop: hold, sync on change, and back off 1 s -> 60 s while anything fails, so a
    platform that is down or an endpoint an older build lacks (404) is asked at most once a minute."""
    cursor: dict | None = None
    backoff = 1.0
    while keep_going():
        try:
            cursor = step(db, cursor)
            backoff = 1.0
        except Exception as exc:  # keep the loop alive; the next request retries
            logger.warning("platform watch: %s — retrying in %.0fs", exc, backoff)
            sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX_SECONDS)


def start_platform_watch(db: Path) -> threading.Thread | None:
    """Run the watch forever in a daemon thread — only when platform-control is configured and no
    other process on this host already runs it."""
    global _singleton
    if not configured():
        return None
    handle = _claim(db)
    if handle is None:
        logger.info("platform watch: another process already holds it")
        return None
    _singleton = handle
    _make_audible()
    thread = threading.Thread(target=run_forever, args=(db,), name="platform-watch", daemon=True)
    thread.start()
    logger.info("platform watch: started")
    return thread
