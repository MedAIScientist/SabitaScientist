"""Authentication utilities: password hashing and opaque session tokens."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from pathlib import Path

import bcrypt

from .db import get_db


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Return True if *password* matches *hashed*."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token() -> str:
    """Generate a cryptographically secure 64-char hex token."""
    return secrets.token_hex(32)


def validate_token(token: str, db_path: Path | None = None) -> str | None:
    """Return user_id if *token* exists and is not expired, else None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT user_id, expires_at FROM auth_tokens WHERE token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if datetime.now(UTC) > expires_at:
        return None
    return row["user_id"]
