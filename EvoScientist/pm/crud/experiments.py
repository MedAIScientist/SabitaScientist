"""CRUD operations for Experiment entities and task-linking."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Experiment, Task


def create_experiment(
    db_path: Path,
    project_id: str,
    name: str,
    created_by: str,
    hypothesis: str | None = None,
    protocol: str | None = None,
    status: str = "planned",
    tags: list[str] | None = None,
    deadline: str | None = None,
) -> Experiment:
    """Create an experiment record and return it."""
    exp_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    tags_json = json.dumps(tags or [])
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO experiments
               (id, project_id, name, hypothesis, protocol, status, tags,
                deadline, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (exp_id, project_id, name, hypothesis, protocol, status,
             tags_json, deadline, created_by, now, now),
        )
    return Experiment(
        id=exp_id,
        project_id=project_id,
        name=name,
        hypothesis=hypothesis,
        protocol=protocol,
        status=status,
        tags=tags or [],
        deadline=deadline,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def get_experiment(db_path: Path, exp_id: str) -> Experiment | None:
    """Return Experiment by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (exp_id,)
        ).fetchone()
    return _row_to_experiment(row) if row else None


def list_experiments(db_path: Path, project_id: str) -> list[Experiment]:
    """Return all experiments for a project, newest first."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM experiments WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    return [_row_to_experiment(r) for r in rows]


def update_experiment(
    db_path: Path,
    exp_id: str,
    name: str | None = None,
    hypothesis: str | None = None,
    protocol: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
    deadline: str | None = None,
) -> Experiment:
    """Update experiment fields. Omitted kwargs are unchanged."""
    exp = get_experiment(db_path, exp_id)
    if exp is None:
        raise ValueError(f"Experiment {exp_id!r} not found")
    now = datetime.now(UTC).isoformat()
    new = Experiment(
        id=exp.id,
        project_id=exp.project_id,
        name=name if name is not None else exp.name,
        hypothesis=hypothesis if hypothesis is not None else exp.hypothesis,
        protocol=protocol if protocol is not None else exp.protocol,
        status=status if status is not None else exp.status,
        tags=tags if tags is not None else exp.tags,
        deadline=deadline if deadline is not None else exp.deadline,
        created_by=exp.created_by,
        created_at=exp.created_at,
        updated_at=now,
    )
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE experiments SET name=?, hypothesis=?, protocol=?, status=?,
               tags=?, deadline=?, updated_at=? WHERE id=?""",
            (new.name, new.hypothesis, new.protocol, new.status,
             json.dumps(new.tags), new.deadline, now, exp_id),
        )
    return new


def delete_experiment(db_path: Path, exp_id: str) -> bool:
    """Delete an experiment (cascades to entries and task links). Returns True if deleted."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM experiments WHERE id = ?", (exp_id,))
    return cur.rowcount > 0


def link_task(db_path: Path, exp_id: str, task_id: str, linked_by: str) -> None:
    """Link a task to an experiment. Raises ValueError if already linked."""
    now = datetime.now(UTC).isoformat()
    try:
        with get_db(db_path) as conn:
            conn.execute(
                "INSERT INTO experiment_tasks (experiment_id, task_id, linked_at, linked_by) VALUES (?, ?, ?, ?)",
                (exp_id, task_id, now, linked_by),
            )
    except Exception as exc:
        if "UNIQUE" in str(exc) or "PRIMARY KEY" in str(exc):
            raise ValueError(f"Task {task_id!r} is already linked to experiment {exp_id!r}") from exc
        raise


def unlink_task(db_path: Path, exp_id: str, task_id: str) -> bool:
    """Remove a task link. Returns True if the link existed."""
    with get_db(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM experiment_tasks WHERE experiment_id = ? AND task_id = ?",
            (exp_id, task_id),
        )
    return cur.rowcount > 0


def list_linked_tasks(db_path: Path, exp_id: str) -> list[Task]:
    """Return all tasks linked to an experiment, ordered by link time."""
    from ..crud.tasks import _row_to_task  # local import to avoid circular
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT t.* FROM tasks t
               JOIN experiment_tasks et ON et.task_id = t.id
               WHERE et.experiment_id = ?
               ORDER BY et.linked_at ASC""",
            (exp_id,),
        ).fetchall()
    return [_row_to_task(r) for r in rows]


def _row_to_experiment(row: sqlite3.Row) -> Experiment:
    try:
        tags = json.loads(row["tags"])
    except Exception:
        tags = []
    return Experiment(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        hypothesis=row["hypothesis"],
        protocol=row["protocol"],
        status=row["status"],
        tags=tags,
        deadline=row["deadline"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
