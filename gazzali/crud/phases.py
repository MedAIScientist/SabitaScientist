"""CRUD operations for ProjectPhase entities."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import ProjectPhase


def _row_to_phase(row) -> ProjectPhase:
    return ProjectPhase(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        color=row["color"],
        position=row["position"],
        target_date=row["target_date"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def create_phase(
    db_path: Path,
    project_id: str,
    name: str,
    color: str,
    position: int,
    target_date: str | None,
    created_by: str,
) -> ProjectPhase:
    """Insert a new phase and return it."""
    phase_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO project_phases
               (id, project_id, name, color, position, target_date, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (phase_id, project_id, name, color, position, target_date, created_by, now),
        )
    return ProjectPhase(
        id=phase_id, project_id=project_id, name=name, color=color,
        position=position, target_date=target_date, created_by=created_by, created_at=now,
    )


def list_phases(db_path: Path, project_id: str) -> list[ProjectPhase]:
    """Return phases for a project ordered by position."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM project_phases WHERE project_id = ? ORDER BY position ASC",
            (project_id,),
        ).fetchall()
    return [_row_to_phase(r) for r in rows]


def get_phase(db_path: Path, phase_id: str) -> ProjectPhase | None:
    """Return a phase by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM project_phases WHERE id = ?", (phase_id,)
        ).fetchone()
    return _row_to_phase(row) if row else None


def update_phase(db_path: Path, phase_id: str, **kwargs) -> ProjectPhase:
    """Update phase fields. Only keys in kwargs are modified."""
    allowed = {"name", "color", "position", "target_date"}
    unknown = set(kwargs) - allowed
    if unknown:
        raise ValueError(f"Unknown phase fields: {unknown}")
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [phase_id]
        with get_db(db_path) as conn:
            conn.execute(
                f"UPDATE project_phases SET {set_clause} WHERE id = ?", values
            )
    phase = get_phase(db_path, phase_id)
    if phase is None:
        raise ValueError(f"Phase {phase_id!r} not found")
    return phase


def delete_phase(db_path: Path, phase_id: str) -> bool:
    """Delete a phase; owned tasks/experiments have phase_id set to NULL by FK."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM project_phases WHERE id = ?", (phase_id,))
    return cur.rowcount > 0


def assign_task_phase(db_path: Path, task_id: str, phase_id: str | None) -> None:
    """Assign or unassign a task to a phase. No-op if task_id does not exist."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE tasks SET phase_id = ? WHERE id = ?", (phase_id, task_id)
        )


def assign_experiment_phase(db_path: Path, experiment_id: str, phase_id: str | None) -> None:
    """Assign or unassign an experiment to a phase. No-op if experiment_id does not exist."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE experiments SET phase_id = ? WHERE id = ?", (phase_id, experiment_id)
        )
