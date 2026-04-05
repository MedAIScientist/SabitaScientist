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


def delete_user(db_path: Path, user_id: str) -> bool:
    """Delete a user by id. Returns True if a row was deleted."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return cur.rowcount > 0


def update_user_password(db_path: Path, user_id: str, new_hash: str) -> None:
    """Update the password_hash for a user."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id),
        )


def _row_to_user(row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        is_admin=bool(row["is_admin"]),
        created_at=row["created_at"],
    )
