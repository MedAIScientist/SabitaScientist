"""CRUD operations for grant milestones, reports and deliverables."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import GrantMilestone

KINDS = ("milestone", "report", "deliverable")

_UPDATE_COLUMNS = (
    "title",
    "kind",
    "due_date",
    "completed_at",
    "owner_id",
    "notes",
    "position",
)


def _row_to_milestone(r) -> GrantMilestone:
    return GrantMilestone(
        id=r["id"],
        grant_id=r["grant_id"],
        title=r["title"],
        kind=r["kind"],
        due_date=r["due_date"],
        completed_at=r["completed_at"],
        owner_id=r["owner_id"],
        notes=r["notes"],
        position=r["position"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def create_milestone(
    db_path: Path,
    grant_id: str,
    title: str,
    kind: str = "milestone",
    due_date: str | None = None,
    owner_id: str | None = None,
    notes: str | None = None,
    position: int = 0,
) -> GrantMilestone:
    """Insert a milestone and return it."""
    mid = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO grant_milestones
               (id,grant_id,title,kind,due_date,completed_at,owner_id,notes,position,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                mid,
                grant_id,
                title,
                kind,
                due_date,
                None,
                owner_id,
                notes,
                position,
                now,
                now,
            ),
        )
    return GrantMilestone(
        id=mid,
        grant_id=grant_id,
        title=title,
        kind=kind,
        due_date=due_date,
        completed_at=None,
        owner_id=owner_id,
        notes=notes,
        position=position,
        created_at=now,
        updated_at=now,
    )


def list_milestones(db_path: Path, grant_id: str) -> list[GrantMilestone]:
    """Return a grant's milestones, soonest due first with undated ones last."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM grant_milestones WHERE grant_id=?
               ORDER BY (due_date IS NULL), due_date, position, created_at""",
            (grant_id,),
        ).fetchall()
    return [_row_to_milestone(r) for r in rows]


def get_milestone(db_path: Path, mid: str) -> GrantMilestone | None:
    with get_db(db_path) as conn:
        r = conn.execute("SELECT * FROM grant_milestones WHERE id=?", (mid,)).fetchone()
    return _row_to_milestone(r) if r else None


def update_milestone(db_path: Path, mid: str, fields: dict) -> GrantMilestone | None:
    """Apply the given column changes; returns the row, or None if unknown."""
    updates = {k: v for k, v in fields.items() if k in _UPDATE_COLUMNS}
    if updates:
        now = datetime.now(UTC).isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        with get_db(db_path) as conn:
            conn.execute(
                f"UPDATE grant_milestones SET {set_clause}, updated_at=? WHERE id=?",
                [*updates.values(), now, mid],
            )
    return get_milestone(db_path, mid)


def delete_milestone(db_path: Path, mid: str) -> bool:
    with get_db(db_path) as conn:
        return (
            conn.execute("DELETE FROM grant_milestones WHERE id=?", (mid,)).rowcount > 0
        )
