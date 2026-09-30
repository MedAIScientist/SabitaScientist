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
        "experiment_assists", "experiment_metrics",
        "project_phases", "task_dependencies",
        "attachments", "admissions",
        "labs", "lab_members",
        "publications", "publication_versions", "publication_reviews",
        "publication_experiments",
        "audit_log",
        "grants", "conferences", "irb_approvals", "lab_wiki_pages",
        "deid_pipelines", "deid_pipeline_runs",
        "sandboxes", "export_requests",
        "task_history", "cvat_projects", "webknossos_datasets",
        "rate_limits",
        "datasets", "dataset_irbs", "dataset_grants",
        "researcher_pushes",
        "grant_budget_items", "grant_milestones", "grant_members",
        "experiment_assets",
        "supervisor_assignments", "weekly_meeting_settings",
        "weekly_reports", "weekly_report_items",
        "meeting_attendance", "report_extensions",
        "academic_journeys", "graduation_requirements",
        "ai_usage",
    }


def test_publications_has_the_submission_compliance_columns(tmp_path: Path) -> None:
    """The readiness gate reads these, so their absence would silently pass papers."""
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    conn = sqlite3.connect(db_path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(publications)")}
    conn.close()

    assert {
        "reporting_guideline",
        "data_availability",
        "code_availability",
        "conflict_of_interest",
        "funding_statement",
    } <= cols


def test_create_schema_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    create_schema(db_path)  # second call must not raise

    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    assert len(cur.fetchall()) == 52
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
