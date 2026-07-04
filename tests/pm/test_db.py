"""Tests for PM database schema creation."""
import sqlite3
from pathlib import Path

import pytest

from EvoScientist.pm.db import create_schema


def test_create_schema_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cur.fetchall()}
    conn.close()

    assert tables == {
        "auth_tokens", "project_members", "projects", "runs",
        "task_comments", "tasks", "users",
        "experiments", "experiment_tasks", "experiment_entries",
        "experiment_assists",
        "project_phases", "task_dependencies",
        "attachments", "admissions",
        "labs", "lab_members",
        "publications", "publication_versions", "publication_reviews",
    }


def test_create_schema_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    create_schema(db_path)  # second call must not raise

    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    assert len(cur.fetchall()) == 20
    conn.close()


def test_project_phases_table_exists(tmp_path):
    from EvoScientist.pm.db import create_schema
    db = tmp_path / "t.db"
    create_schema(db)
    import sqlite3
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "project_phases" in tables
    assert "task_dependencies" in tables
    conn.close()

def test_tasks_has_phase_id_column(tmp_path):
    from EvoScientist.pm.db import create_schema
    db = tmp_path / "t.db"
    create_schema(db)
    import sqlite3
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    assert "phase_id" in cols
    conn.close()

def test_experiments_has_phase_id_column(tmp_path):
    from EvoScientist.pm.db import create_schema
    db = tmp_path / "t.db"
    create_schema(db)
    import sqlite3
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(experiments)").fetchall()}
    assert "phase_id" in cols
    conn.close()

def test_create_schema_idempotent_with_migrations(tmp_path):
    from EvoScientist.pm.db import create_schema
    db = tmp_path / "t.db"
    create_schema(db)
    create_schema(db)  # second call must not raise


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
        conn.commit()
    conn.close()
