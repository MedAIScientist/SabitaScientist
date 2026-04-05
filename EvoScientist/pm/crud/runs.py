"""CRUD operations for Run entities."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Run


def create_run(
    db_path: Path,
    task_id: str,
    project_id: str,
    agent_type: str,
    prompt: str,
    created_by: str,
) -> Run:
    """Create a run record with status 'pending' and return it."""
    run_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO runs (id, task_id, project_id, agent_type, prompt,
               status, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (run_id, task_id, project_id, agent_type, prompt, created_by, now),
        )
    return Run(
        id=run_id,
        task_id=task_id,
        project_id=project_id,
        agent_type=agent_type,
        prompt=prompt,
        status="pending",
        created_by=created_by,
        created_at=now,
    )


def get_run(db_path: Path, run_id: str) -> Run | None:
    """Return Run by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return _row_to_run(row) if row else None


def list_runs_for_task(db_path: Path, task_id: str) -> list[Run]:
    """Return all runs for a task, newest first."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE task_id = ? ORDER BY created_at DESC",
            (task_id,),
        ).fetchall()
    return [_row_to_run(r) for r in rows]


def update_run_status(db_path: Path, run_id: str, status: str) -> None:
    """Update run status; sets started_at when transitioning to 'running'."""
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        if status == "running":
            conn.execute(
                "UPDATE runs SET status=?, started_at=? WHERE id=?",
                (status, now, run_id),
            )
        else:
            conn.execute("UPDATE runs SET status=? WHERE id=?", (status, run_id))


def update_run_output(
    db_path: Path, run_id: str, status: str, output: str, error: str | None = None
) -> None:
    """Save final output and terminal status (done/failed/cancelled)."""
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE runs SET status=?, output=?, error=?, finished_at=? WHERE id=?",
            (status, output, error, now, run_id),
        )


def _row_to_run(row) -> Run:
    return Run(
        id=row["id"],
        task_id=row["task_id"],
        project_id=row["project_id"],
        agent_type=row["agent_type"],
        prompt=row["prompt"],
        status=row["status"],
        output=row["output"],
        error=row["error"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )
