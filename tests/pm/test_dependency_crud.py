"""Tests for TaskDependency CRUD operations."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from EvoScientist.pm.crud.dependencies import (
    add_dependency,
    get_blocked_by,
    list_dependencies,
    list_dependents,
    remove_dependency,
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
    # Three tasks for cycle testing: A -> B -> C -> A
    for tid, title in [("tA", "Task A"), ("tB", "Task B"), ("tC", "Task C")]:
        conn.execute(
            """INSERT INTO tasks
               (id, project_id, title, status, priority, created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (tid, "p1", title, "todo", "medium", "u1", now, now),
        )
    conn.commit()
    conn.close()
    return path


def test_add_dependency_hard(db_path):
    dep = add_dependency(db_path, task_id="tA", depends_on_id="tB",
                         dep_type="hard", created_by="u1")
    assert dep.task_id == "tA"
    assert dep.depends_on_id == "tB"
    assert dep.dep_type == "hard"
    assert dep.created_by == "u1"
    assert dep.created_at


def test_add_dependency_soft(db_path):
    dep = add_dependency(db_path, task_id="tA", depends_on_id="tB",
                         dep_type="soft", created_by="u1")
    assert dep.dep_type == "soft"


def test_add_dependency_invalid_type(db_path):
    with pytest.raises(ValueError):
        add_dependency(db_path, task_id="tA", depends_on_id="tB",
                       dep_type="invalid", created_by="u1")


def test_add_dependency_self(db_path):
    with pytest.raises(ValueError, match="cannot depend on itself"):
        add_dependency(db_path, task_id="tA", depends_on_id="tA",
                       dep_type="hard", created_by="u1")


def test_add_dependency_cycle(db_path):
    # A depends on B, B depends on C, then C depends on A would create a cycle
    add_dependency(db_path, task_id="tA", depends_on_id="tB",
                   dep_type="hard", created_by="u1")
    add_dependency(db_path, task_id="tB", depends_on_id="tC",
                   dep_type="hard", created_by="u1")
    with pytest.raises(ValueError, match="cycle"):
        add_dependency(db_path, task_id="tC", depends_on_id="tA",
                       dep_type="hard", created_by="u1")


def test_remove_dependency(db_path):
    add_dependency(db_path, task_id="tA", depends_on_id="tB",
                   dep_type="hard", created_by="u1")
    result = remove_dependency(db_path, task_id="tA", depends_on_id="tB")
    assert result is True


def test_remove_dependency_not_found(db_path):
    result = remove_dependency(db_path, task_id="tA", depends_on_id="tB")
    assert result is False


def test_list_dependencies(db_path):
    add_dependency(db_path, task_id="tA", depends_on_id="tB",
                   dep_type="hard", created_by="u1")
    add_dependency(db_path, task_id="tA", depends_on_id="tC",
                   dep_type="soft", created_by="u1")
    deps = list_dependencies(db_path, task_id="tA")
    assert len(deps) == 2
    depends_on_ids = {d.depends_on_id for d in deps}
    assert depends_on_ids == {"tB", "tC"}


def test_list_dependents(db_path):
    # Both tA and tB depend on tC
    add_dependency(db_path, task_id="tA", depends_on_id="tC",
                   dep_type="hard", created_by="u1")
    add_dependency(db_path, task_id="tB", depends_on_id="tC",
                   dep_type="soft", created_by="u1")
    dependents = list_dependents(db_path, task_id="tC")
    assert len(dependents) == 2
    task_ids = {d.task_id for d in dependents}
    assert task_ids == {"tA", "tB"}


def test_get_blocked_by(db_path):
    # tA has a hard dep on tB and a soft dep on tC
    add_dependency(db_path, task_id="tA", depends_on_id="tB",
                   dep_type="hard", created_by="u1")
    add_dependency(db_path, task_id="tA", depends_on_id="tC",
                   dep_type="soft", created_by="u1")
    blocked = get_blocked_by(db_path, task_id="tA")
    # Only hard deps should be returned
    assert blocked == ["tB"]
