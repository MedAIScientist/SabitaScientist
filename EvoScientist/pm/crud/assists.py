"""CRUD operations for ExperimentAssist entities."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import ExperimentAssist

TERMINAL_STATUSES = frozenset({"done", "failed", "cancelled"})


def _row_to_assist(row: sqlite3.Row) -> ExperimentAssist:
    return ExperimentAssist(
        id=row["id"],
        experiment_id=row["experiment_id"],
        project_id=row["project_id"],
        prompt=row["prompt"],
        context_json=row["context_json"],
        status=row["status"],
        output=row["output"],
        error=row["error"],
        agent_type=row.get("agent_type", "writing"),
        target_field=row["target_field"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        finished_at=row["finished_at"],
    )


def create_assist(
    db_path: Path,
    experiment_id: str,
    project_id: str,
    prompt: str,
    context_json: str,
    agent_type: str = "writing",
    target_field: str | None = None,
    created_by: str = "agent",
) -> ExperimentAssist:
    """Insert a new assist record with status 'pending' and return it."""
    assist_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO experiment_assists
               (id, experiment_id, project_id, prompt, context_json,
                status, agent_type, target_field, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
            (assist_id, experiment_id, project_id, prompt, context_json,
             agent_type, target_field, created_by, now),
        )
    return ExperimentAssist(
        id=assist_id,
        experiment_id=experiment_id,
        project_id=project_id,
        prompt=prompt,
        context_json=context_json,
        status="pending",
        agent_type=agent_type,
        target_field=target_field,
        created_by=created_by,
        created_at=now,
    )


def get_assist(db_path: Path, assist_id: str) -> ExperimentAssist | None:
    """Return ExperimentAssist by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM experiment_assists WHERE id = ?", (assist_id,)
        ).fetchone()
    return _row_to_assist(row) if row else None


def list_assists_for_experiment(
    db_path: Path, experiment_id: str
) -> list[ExperimentAssist]:
    """Return all assists for an experiment, newest first."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM experiment_assists
               WHERE experiment_id = ? ORDER BY created_at DESC""",
            (experiment_id,),
        ).fetchall()
    return [_row_to_assist(r) for r in rows]


def update_assist_status(db_path: Path, assist_id: str, status: str) -> None:
    """Update assist status; sets finished_at when terminal."""
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        if status in TERMINAL_STATUSES:
            conn.execute(
                "UPDATE experiment_assists SET status = ?, finished_at = ? WHERE id = ?",
                (status, now, assist_id),
            )
        else:
            conn.execute(
                "UPDATE experiment_assists SET status = ? WHERE id = ?",
                (status, assist_id),
            )


def update_assist_output(
    db_path: Path, assist_id: str, status: str, output: str, error: str | None = None
) -> None:
    """Save final output and terminal status."""
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE experiment_assists
               SET status = ?, output = ?, error = ?, finished_at = ?
               WHERE id = ?""",
            (status, output, error, now, assist_id),
        )
