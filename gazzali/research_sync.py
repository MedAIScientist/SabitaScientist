"""Keep AutoResearchClaw runs moving: refresh state, dispatch the queue, notify deciders.

``sync_once`` is what the background thread (``python -m gazzali``) runs every
30 s; the API also refreshes a run whenever someone reads it.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import research_claw as arc
from . import settings
from .crud import research_runs as runs_db
from .db import get_db

logger = logging.getLogger(__name__)

# The free NVIDIA key allows ~40 requests/minute for everything; one ARC run at a
# time leaves room for the copilot and drafting. Waiting runs do not count.
USAGE_LIMIT_PER_MINUTE = 40


def max_concurrent() -> int:
    return max(1, int(os.environ.get("ARC_MAX_CONCURRENT", "1")))


def refresh(db: Path, run: dict) -> dict:
    """Pull the worker's view of an active run; import results once it ends."""
    if run["status"] in runs_db.ACTIVE:
        try:
            runs_db.update_from_worker(db, run["id"], arc.status(run["id"]))
        except arc.WorkerError:
            return run  # worker down: show the last known state
        run = runs_db.get_run(db, run["id"]) or run
        if run["status"] == "waiting" and run["notified_stage"] != run["stage"]:
            notify_deciders(db, run)
    if run["status"] in ("done", "failed") and not run["imported_at"]:
        try:
            arc.import_results(db, run)
        except arc.WorkerError:
            pass
        run = runs_db.get_run(db, run["id"]) or run
    return run


def dispatch(db: Path) -> None:
    """Send queued runs to the worker, oldest first, while capacity allows."""
    open_runs = runs_db.list_open_runs(db)
    running = sum(1 for r in open_runs if r["status"] == "running")
    for run in (r for r in open_runs if r["status"] == "queued"):
        if running >= max_concurrent():
            return
        try:
            arc.start(run["id"], run["topic"], run["mode"], run["dataset"],
                      arc.lab_lessons_to_seed(db, run["lab_id"]), run["domain"])
        except arc.WorkerError as exc:
            if exc.retryable:
                return  # worker down: keep the queue as it is
            runs_db.set_status(db, run["id"], "failed", str(exc))
            continue
        runs_db.set_status(db, run["id"], "running")
        running += 1


def deciders(db: Path, run: dict) -> list[dict]:
    """Who decides this gate: a lab PI from stage 14 on, else the project owner/editors."""
    with get_db(db) as conn:
        if arc.is_post_experiment_gate(run["stage"]) and run["lab_id"]:
            rows = conn.execute(
                """SELECT DISTINCT u.id, u.email, u.username FROM users u
                    WHERE u.id = (SELECT pi_id FROM labs WHERE id = ?)
                       OR u.id IN (SELECT user_id FROM lab_members WHERE lab_id = ?
                                   AND ended_at IS NULL AND role IN ('pi', 'admin'))""",
                (run["lab_id"], run["lab_id"]),
            ).fetchall()
        else:
            roles = ("owner",) if arc.is_post_experiment_gate(run["stage"]) else ("owner", "editor")
            rows = conn.execute(
                f"""SELECT u.id, u.email, u.username FROM users u JOIN project_members m ON m.user_id = u.id
                     WHERE m.project_id = ? AND m.role IN ({','.join('?' * len(roles))})""",
                (run["project_id"], *roles),
            ).fetchall()
    return [dict(r) for r in rows]


def notify_deciders(db: Path, run: dict) -> None:
    """E-mail the deciders once per gate (in-app they see it in the gates inbox)."""
    from .notifications import send_email

    base = settings.get_smtp_config()["base_url"].rstrip("/")
    stage = f"stage {run['stage']} ({(run['stage_name'] or '').replace('_', ' ').lower()})"
    for user in deciders(db, run):
        if user.get("email"):
            send_email(
                user["email"],
                f"[Gazzali] A research run needs your decision at {stage}",
                f"AutoResearchClaw is waiting for a decision on:\n\n{run['topic']}\n\n"
                f"Open {base}/ to review it (Research gates on your home page).",
            )
    runs_db.set_notified(db, run["id"], run["stage"])


def usage(db: Path) -> dict:
    """What the shared LLM quota is being used for right now."""
    since = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
    with get_db(db) as conn:
        recent = conn.execute("SELECT COUNT(*) FROM ai_usage WHERE created_at >= ?", (since,)).fetchone()[0]
    open_runs = runs_db.list_open_runs(db)
    return {
        "requests_last_minute": recent,
        "limit_per_minute": USAGE_LIMIT_PER_MINUTE,
        "runs_running": sum(1 for r in open_runs if r["status"] == "running"),
        "runs_waiting": sum(1 for r in open_runs if r["status"] == "waiting"),
        "runs_queued": sum(1 for r in open_runs if r["status"] == "queued"),
        "max_concurrent": max_concurrent(),
    }


def sync_once(db: Path) -> None:
    for run in runs_db.list_active_runs(db):
        refresh(db, run)
    dispatch(db)


def start_background_sync(db: Path, interval: float = 30.0) -> threading.Thread:
    """Run ``sync_once`` forever in a daemon thread (only if the worker is configured)."""

    def loop() -> None:
        while True:
            try:
                sync_once(db)
            except Exception:  # keep the loop alive; the next tick retries
                logger.exception("research sync failed")
            time.sleep(interval)

    thread = threading.Thread(target=loop, name="research-sync", daemon=True)
    thread.start()
    return thread
