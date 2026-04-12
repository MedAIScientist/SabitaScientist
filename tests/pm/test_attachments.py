"""Tests for attachment CRUD operations."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from EvoScientist.pm.crud.attachments import (
    create_attachment,
    delete_attachment,
    get_attachment,
    list_attachments,
)
from EvoScientist.pm.db import create_schema


@pytest.fixture
def db(tmp_path: Path):
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Insert prerequisite rows
    conn.execute(
        "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?)",
        ("user1", "alice", "hash", 0, "2024-01-01T00:00:00"),
    )
    conn.execute(
        "INSERT INTO projects (id, name, created_by, created_at) VALUES (?, ?, ?, ?)",
        ("proj1", "Test Project", "user1", "2024-01-01T00:00:00"),
    )
    conn.execute(
        "INSERT INTO project_members (project_id, user_id, role, added_at) VALUES (?, ?, ?, ?)",
        ("proj1", "user1", "owner", "2024-01-01T00:00:00"),
    )
    conn.execute(
        """INSERT INTO experiments (id, project_id, name, status, tags, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("exp1", "proj1", "Exp 1", "planned", "[]", "user1", "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
    )
    conn.execute(
        """INSERT INTO experiment_entries (id, experiment_id, type, title, body, author_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("entry1", "exp1", "note", "Note 1", "body text", "user1", "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
    )
    conn.commit()
    yield conn
    conn.close()


def test_create_attachment(db):
    att = create_attachment(
        db, entry_id="entry1", filename="plot.png",
        s3_key="entries/entry1/abc/plot.png",
        content_type="image/png", size_bytes=1024, user_id="user1",
    )
    assert att.id
    assert att.entry_id == "entry1"
    assert att.filename == "plot.png"
    assert att.s3_key == "entries/entry1/abc/plot.png"
    assert att.content_type == "image/png"
    assert att.size_bytes == 1024
    assert att.uploaded_by == "user1"
    assert att.created_at


def test_list_attachments_empty(db):
    result = list_attachments(db, "entry1")
    assert result == []


def test_list_attachments(db):
    create_attachment(db, "entry1", "a.txt", "k1", "text/plain", 10, "user1")
    create_attachment(db, "entry1", "b.csv", "k2", "text/csv", 20, "user1")
    result = list_attachments(db, "entry1")
    assert len(result) == 2
    assert result[0].filename == "a.txt"
    assert result[1].filename == "b.csv"


def test_get_attachment(db):
    att = create_attachment(db, "entry1", "data.json", "k3", "application/json", 512, None)
    fetched = get_attachment(db, att.id)
    assert fetched is not None
    assert fetched.id == att.id
    assert fetched.filename == "data.json"
    assert fetched.uploaded_by is None


def test_get_attachment_not_found(db):
    assert get_attachment(db, "nonexistent-id") is None


def test_delete_attachment(db):
    att = create_attachment(db, "entry1", "to_delete.pdf", "k4", "application/pdf", 100, "user1")
    delete_attachment(db, att.id)
    assert get_attachment(db, att.id) is None


def test_attachment_cascades_with_entry_delete(db):
    """Deleting an entry should cascade-delete its attachments."""
    att = create_attachment(db, "entry1", "cascade.png", "k5", "image/png", 200, "user1")
    assert get_attachment(db, att.id) is not None
    db.execute("DELETE FROM experiment_entries WHERE id = 'entry1'")
    db.commit()
    assert get_attachment(db, att.id) is None
