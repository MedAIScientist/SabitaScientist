"""CRUD operations for User entities."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import User


def create_user(
    db_path: Path,
    username: str,
    password_hash: str,
    email: str | None = None,
    is_admin: bool = False,
) -> User:
    """Insert a new user and return the created User."""
    user_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO users (id, username, email, password_hash, is_admin, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, email, password_hash, int(is_admin), now),
        )
    return User(
        id=user_id,
        username=username,
        email=email,
        password_hash=password_hash,
        is_admin=is_admin,
        created_at=now,
    )


def get_user_by_id(db_path: Path, user_id: str) -> User | None:
    """Return User by primary key, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, username, email, password_hash, is_admin, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_username(db_path: Path, username: str) -> User | None:
    """Return User by username, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, username, email, password_hash, is_admin, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return _row_to_user(row) if row else None


def list_users(db_path: Path) -> list[User]:
    """Return all users ordered by username."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, username, email, password_hash, is_admin, created_at FROM users ORDER BY username",
        ).fetchall()
    return [_row_to_user(r) for r in rows]


def search_users(db_path: Path, q: str, limit: int = 20) -> list[User]:
    """Return users whose username contains q (case-insensitive), up to limit."""
    if not q:
        return []
    q = q[:64]
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT id, username, email, password_hash, is_admin, created_at
               FROM users WHERE username LIKE ? ESCAPE '\\' ORDER BY username LIMIT ?""",
            (f"%{escaped}%", limit),
        ).fetchall()
    return [_row_to_user(r) for r in rows]


def delete_user(db_path: Path, user_id: str) -> bool:
    """Delete a user by id. Nulls out foreign key references first. Returns True if a row was deleted."""
    with get_db(db_path) as conn:
        # Nullable FK columns referencing users
        conn.execute("UPDATE tasks SET assignee_id = NULL WHERE assignee_id = ?", (user_id,))
        conn.execute("UPDATE tasks SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE task_comments SET author_id = NULL WHERE author_id = ?", (user_id,))
        conn.execute("UPDATE runs SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE experiments SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE experiment_entries SET author_id = NULL WHERE author_id = ?", (user_id,))
        conn.execute("UPDATE experiment_assists SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE project_phases SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE task_dependencies SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE attachments SET uploaded_by = NULL WHERE uploaded_by = ?", (user_id,))
        conn.execute("UPDATE admissions SET reviewer_id = NULL WHERE reviewer_id = ?", (user_id,))
        conn.execute("UPDATE labs SET pi_id = NULL WHERE pi_id = ?", (user_id,))
        conn.execute("UPDATE publications SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE publication_versions SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE grants SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE grants SET pi_id = NULL WHERE pi_id = ?", (user_id,))
        conn.execute("UPDATE conferences SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE irb_approvals SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE lab_wiki_pages SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE deid_pipelines SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE deid_pipeline_runs SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE sandboxes SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE sandboxes SET terminated_by = NULL WHERE terminated_by = ?", (user_id,))
        conn.execute("UPDATE export_requests SET requested_by = NULL WHERE requested_by = ?", (user_id,))
        conn.execute("UPDATE export_requests SET reviewed_by = NULL WHERE reviewed_by = ?", (user_id,))
        conn.execute("UPDATE task_history SET changed_by = NULL WHERE changed_by = ?", (user_id,))
        conn.execute("UPDATE cvat_projects SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE webknossos_datasets SET created_by = NULL WHERE created_by = ?", (user_id,))
        conn.execute("UPDATE audit_log SET user_id = NULL WHERE user_id = ?", (user_id,))
        conn.execute("UPDATE auth_tokens SET user_id = NULL WHERE user_id = ?", (user_id,))

        # Junction tables — delete membership rows directly
        conn.execute("DELETE FROM project_members WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM lab_members WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM experiment_tasks WHERE linked_by = ?", (user_id,))

        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return cur.rowcount > 0


def update_user_password(db_path: Path, user_id: str, new_hash: str) -> None:
    """Update the password_hash for a user."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id),
        )


def update_user(
    db_path: Path,
    user_id: str,
    username: str | None = None,
    email: str | None = None,
    is_admin: bool | None = None,
) -> User | None:
    """Update user fields. Returns updated User or None if not found."""
    fields: list[str] = []
    params: list = []
    if username is not None:
        fields.append("username = ?")
        params.append(username)
    if email is not None:
        fields.append("email = ?")
        params.append(email)
    if is_admin is not None:
        fields.append("is_admin = ?")
        params.append(int(is_admin))
    if not fields:
        return get_user_by_id(db_path, user_id)
    params.append(user_id)
    with get_db(db_path) as conn:
        conn.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE id = ?",
            params,
        )
    return get_user_by_id(db_path, user_id)


def _row_to_user(row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        is_admin=bool(row["is_admin"]),
        created_at=row["created_at"],
    )
