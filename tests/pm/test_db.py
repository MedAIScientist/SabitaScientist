"""Tests for PM database schema creation."""
import pytest
import sqlite3
from pathlib import Path

from EvoScientist.pm.db import create_schema


def test_create_schema_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cur.fetchall()}
    conn.close()

    assert tables == {"auth_tokens", "project_members", "projects", "task_comments", "tasks", "users"}


def test_create_schema_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    create_schema(db_path)  # second call must not raise

    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    assert len(cur.fetchall()) == 6
    conn.close()


def test_foreign_keys_enforced(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO projects (id, name, created_by, created_at) VALUES (?, ?, ?, ?)",
            ("p1", "Test", "nonexistent-user-id", "2026-01-01T00:00:00"),
        )
    conn.close()
