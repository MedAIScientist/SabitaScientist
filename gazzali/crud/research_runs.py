"""research_runs: PM-side mirror of AutoResearchClaw runs (see pm/research_claw.py)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db

ACTIVE = ("running", "waiting")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row(row) -> dict:
    run = dict(row)
    run["waiting"] = json.loads(run.pop("waiting_json") or "null")
    return run


def create_run(
    db: Path, *, experiment_id: str, project_id: str, lab_id: str | None, started_by: str,
    topic: str, mode: str, dataset: str | None, irb_id: str | None,
) -> dict:
    now = _now()
    run_id = uuid.uuid4().hex
    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO research_runs (id, experiment_id, project_id, lab_id, started_by, topic,
                   mode, dataset, irb_id, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)""",
            (run_id, experiment_id, project_id, lab_id, started_by, topic, mode, dataset, irb_id, now, now),
        )
    return get_run(db, run_id) or {}


def get_run(db: Path, run_id: str) -> dict | None:
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone()
    return _row(row) if row else None


def list_runs(db: Path, experiment_id: str) -> list[dict]:
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM research_runs WHERE experiment_id = ? ORDER BY created_at DESC", (experiment_id,)
        ).fetchall()
    return [_row(r) for r in rows]


def list_active_runs(db: Path) -> list[dict]:
    with get_db(db) as conn:
        rows = conn.execute(
            f"SELECT * FROM research_runs WHERE status IN ({','.join('?' * len(ACTIVE))})", ACTIVE
        ).fetchall()
    return [_row(r) for r in rows]


def update_from_worker(db: Path, run_id: str, worker: dict) -> None:
    """Store what the worker reported (its keys: state, stage, stage_name, waiting, error)."""
    with get_db(db) as conn:
        conn.execute(
            """UPDATE research_runs SET status = ?, stage = ?, stage_name = ?, waiting_json = ?,
                   error = ?, updated_at = ? WHERE id = ?""",
            (
                worker["state"], worker.get("stage"), worker.get("stage_name"),
                json.dumps(worker["waiting"]) if worker.get("waiting") else None,
                worker.get("error"), _now(), run_id,
            ),
        )


def set_status(db: Path, run_id: str, status: str, error: str | None = None) -> None:
    with get_db(db) as conn:
        conn.execute(
            "UPDATE research_runs SET status = ?, error = COALESCE(?, error), updated_at = ? WHERE id = ?",
            (status, error, _now(), run_id),
        )


def list_lessons(db: Path, lab_id: str) -> list[dict]:
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT id, run_id, category, severity, lesson_json, created_at FROM research_lessons "
            "WHERE lab_id = ? ORDER BY created_at DESC",
            (lab_id,),
        ).fetchall()
    return [{**dict(r), "lesson": json.loads(r["lesson_json"])} for r in rows]


def delete_lesson(db: Path, lab_id: str, lesson_id: str) -> bool:
    with get_db(db) as conn:
        cur = conn.execute("DELETE FROM research_lessons WHERE id = ? AND lab_id = ?", (lesson_id, lab_id))
    return cur.rowcount > 0
