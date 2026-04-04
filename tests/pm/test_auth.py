"""Tests for PM auth utilities."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from EvoScientist.pm.auth import (
    create_token,
    hash_password,
    validate_token,
    verify_password,
)
from EvoScientist.pm.db import create_schema, get_db


def test_hash_password_returns_string() -> None:
    hashed = hash_password("mysecret")
    assert isinstance(hashed, str)
    assert hashed != "mysecret"


def test_verify_password_correct() -> None:
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_verify_password_wrong() -> None:
    hashed = hash_password("mysecret")
    assert verify_password("wrongpassword", hashed) is False


def test_create_token_length() -> None:
    token = create_token()
    assert len(token) == 64  # 32 bytes hex = 64 chars


def test_create_token_unique() -> None:
    assert create_token() != create_token()


def test_validate_token_valid(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    # Insert a user and a valid token
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?)",
            ("u1", "alice", "hash", 0, "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            ("tok123", "u1", future),
        )

    result = validate_token("tok123", db_path)
    assert result == "u1"


def test_validate_token_expired(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?)",
            ("u1", "alice", "hash", 0, "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            ("tok_old", "u1", past),
        )

    assert validate_token("tok_old", db_path) is None


def test_validate_token_unknown(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    assert validate_token("doesnotexist", db_path) is None
