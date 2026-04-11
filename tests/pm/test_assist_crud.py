"""Tests for ExperimentAssist CRUD operations."""
from __future__ import annotations

from pathlib import Path

import pytest

from EvoScientist.pm.crud.assists import (
    create_assist,
    get_assist,
    list_assists_for_experiment,
    update_assist_output,
    update_assist_status,
)
from EvoScientist.pm.db import create_schema


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    create_schema(path)
    import sqlite3
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    now = "2024-01-01T00:00:00"
    conn.execute(
        "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?,?,?,?,?)",
        ("u1", "alice", "hash", 0, now),
    )
    conn.execute(
        "INSERT INTO projects (id, name, created_by, created_at) VALUES (?,?,?,?)",
        ("p1", "Proj", "u1", now),
    )
    conn.execute(
        "INSERT INTO project_members (project_id, user_id, role, added_at) VALUES (?,?,?,?)",
        ("p1", "u1", "owner", now),
    )
    conn.execute(
        """INSERT INTO experiments (id, project_id, name, status, tags,
           created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
        ("e1", "p1", "Exp 1", "planned", "[]", "u1", now, now),
    )
    conn.commit()
    conn.close()
    return path


def test_create_assist(db_path):
    a = create_assist(db_path, experiment_id="e1", project_id="p1",
                      prompt="Write a hypothesis", context_json='{"name":"Exp 1"}',
                      target_field="hypothesis", created_by="u1")
    assert a.id
    assert a.experiment_id == "e1"
    assert a.project_id == "p1"
    assert a.prompt == "Write a hypothesis"
    assert a.status == "pending"
    assert a.target_field == "hypothesis"
    assert a.output is None


def test_get_assist(db_path):
    a = create_assist(db_path, "e1", "p1", "p", "{}", None, "u1")
    fetched = get_assist(db_path, a.id)
    assert fetched is not None
    assert fetched.id == a.id


def test_get_assist_not_found(db_path):
    assert get_assist(db_path, "nonexistent") is None


def test_list_assists_for_experiment(db_path):
    create_assist(db_path, "e1", "p1", "p1", "{}", None, "u1")
    create_assist(db_path, "e1", "p1", "p2", "{}", None, "u1")
    results = list_assists_for_experiment(db_path, "e1")
    assert len(results) == 2
    # newest first
    assert results[0].created_at >= results[1].created_at


def test_update_assist_status(db_path):
    a = create_assist(db_path, "e1", "p1", "p", "{}", None, "u1")
    update_assist_status(db_path, a.id, "running")
    fetched = get_assist(db_path, a.id)
    assert fetched.status == "running"


def test_update_assist_output(db_path):
    a = create_assist(db_path, "e1", "p1", "p", "{}", None, "u1")
    update_assist_output(db_path, a.id, "done", "Generated text")
    fetched = get_assist(db_path, a.id)
    assert fetched.status == "done"
    assert fetched.output == "Generated text"
    assert fetched.finished_at is not None


def test_cascade_delete(db_path):
    """Deleting experiment should cascade-delete its assists."""
    a = create_assist(db_path, "e1", "p1", "p", "{}", None, "u1")
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM experiments WHERE id = 'e1'")
    conn.commit()
    conn.close()
    assert get_assist(db_path, a.id) is None
