"""CRUD operations for grant team members."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import GrantMember

ROLES = ("pi", "co_pi", "researcher", "assistant", "advisor")

_UPDATE_COLUMNS = ("role", "share_percent")


def _row_to_member(r) -> GrantMember:
    return GrantMember(
        id=r["id"],
        grant_id=r["grant_id"],
        user_id=r["user_id"],
        role=r["role"],
        share_percent=r["share_percent"],
        added_at=r["added_at"],
        username=r["username"] if "username" in r.keys() else None,
    )


def add_member(
    db_path: Path,
    grant_id: str,
    user_id: str,
    role: str = "researcher",
    share_percent: float | None = None,
) -> GrantMember:
    """Add a member to a grant team.

    Raises sqlite3.IntegrityError when the user is already on the team — the
    (grant_id, user_id) UNIQUE constraint is the source of truth, so a duplicate
    is rejected here rather than silently creating a second row.
    """
    member_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO grant_members (id,grant_id,user_id,role,share_percent,added_at)
               VALUES (?,?,?,?,?,?)""",
            (member_id, grant_id, user_id, role, share_percent, now),
        )
    return GrantMember(
        id=member_id,
        grant_id=grant_id,
        user_id=user_id,
        role=role,
        share_percent=share_percent,
        added_at=now,
    )


def list_members(db_path: Path, grant_id: str) -> list[GrantMember]:
    """Return a grant's team with usernames resolved, PI first."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT m.*, u.username AS username
               FROM grant_members m
               LEFT JOIN users u ON u.id = m.user_id
               WHERE m.grant_id=?
               ORDER BY (m.role <> 'pi'), m.role, u.username""",
            (grant_id,),
        ).fetchall()
    return [_row_to_member(r) for r in rows]


def get_member(db_path: Path, member_id: str) -> GrantMember | None:
    with get_db(db_path) as conn:
        r = conn.execute(
            """SELECT m.*, u.username AS username
               FROM grant_members m
               LEFT JOIN users u ON u.id = m.user_id
               WHERE m.id=?""",
            (member_id,),
        ).fetchone()
    return _row_to_member(r) if r else None


def update_member(db_path: Path, member_id: str, fields: dict) -> GrantMember | None:
    """Apply the given column changes; returns the row, or None if unknown."""
    updates = {k: v for k, v in fields.items() if k in _UPDATE_COLUMNS}
    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        with get_db(db_path) as conn:
            conn.execute(
                f"UPDATE grant_members SET {set_clause} WHERE id=?",
                [*updates.values(), member_id],
            )
    return get_member(db_path, member_id)


def remove_member(db_path: Path, member_id: str) -> bool:
    with get_db(db_path) as conn:
        return (
            conn.execute("DELETE FROM grant_members WHERE id=?", (member_id,)).rowcount
            > 0
        )
