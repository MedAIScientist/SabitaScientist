"""Tests for ProjectPhase CRUD operations."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from EvoScientist.pm.crud.phases import (
    assign_experiment_phase,
    assign_task_phase,
    create_phase,
    delete_phase,
    get_phase,
    list_phases,
    update_phase,
)
from EvoScientist.pm.db import create_schema


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    create_schema(path)
    now = "2024-01-01T00:00:00"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
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
        """INSERT INTO tasks
           (id, project_id, title, status, priority, created_by, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        ("t1", "p1", "Task 1", "todo", "medium", "u1", now, now),
    )
    conn.execute(
        """INSERT INTO experiments (id, project_id, name, status, tags,
           created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
        ("e1", "p1", "Exp 1", "planned", "[]", "u1", now, now),
    )
    conn.commit()
    conn.close()
    return path


def test_create_phase(db_path):
    p = create_phase(db_path, project_id="p1", name="Data Collection",
                     color="#6366f1", position=0, target_date=None, created_by="u1")
    assert p.id
    assert p.project_id == "p1"
    assert p.name == "Data Collection"
    assert p.color == "#6366f1"
    assert p.position == 0
    assert p.target_date is None


def test_list_phases_ordered_by_position(db_path):
    create_phase(db_path, "p1", "Phase B", "#ff0000", 2, None, "u1")
    create_phase(db_path, "p1", "Phase A", "#00ff00", 0, None, "u1")
    create_phase(db_path, "p1", "Phase C", "#0000ff", 1, None, "u1")
    phases = list_phases(db_path, "p1")
    assert [p.position for p in phases] == [0, 1, 2]


def test_get_phase(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    fetched = get_phase(db_path, p.id)
    assert fetched is not None
    assert fetched.id == p.id
    assert fetched.name == "P"


def test_get_phase_not_found(db_path):
    assert get_phase(db_path, "nonexistent") is None


def test_update_phase_name(db_path):
    p = create_phase(db_path, "p1", "Old Name", "#6366f1", 0, None, "u1")
    updated = update_phase(db_path, p.id, name="New Name")
    assert updated.name == "New Name"
    assert updated.color == "#6366f1"


def test_update_phase_target_date(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    updated = update_phase(db_path, p.id, target_date="2024-06-01")
    assert updated.target_date == "2024-06-01"


def test_delete_phase_tasks_become_unphased(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    assign_task_phase(db_path, "t1", p.id)
    delete_phase(db_path, p.id)
    # Phase is gone
    assert get_phase(db_path, p.id) is None
    # Task's phase_id is NULL (SET NULL FK)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT phase_id FROM tasks WHERE id='t1'").fetchone()
    conn.close()
    assert row[0] is None


def test_assign_task_phase(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    assign_task_phase(db_path, "t1", p.id)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT phase_id FROM tasks WHERE id='t1'").fetchone()
    conn.close()
    assert row[0] == p.id


def test_assign_task_phase_unassign(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    assign_task_phase(db_path, "t1", p.id)
    assign_task_phase(db_path, "t1", None)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT phase_id FROM tasks WHERE id='t1'").fetchone()
    conn.close()
    assert row[0] is None


def test_assign_experiment_phase(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    assign_experiment_phase(db_path, "e1", p.id)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT phase_id FROM experiments WHERE id='e1'").fetchone()
    conn.close()
    assert row[0] == p.id


def test_assign_experiment_phase_unassign(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    assign_experiment_phase(db_path, "e1", p.id)
    assign_experiment_phase(db_path, "e1", None)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT phase_id FROM experiments WHERE id='e1'").fetchone()
    conn.close()
    assert row[0] is None
