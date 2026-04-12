"""Tests for Run CRUD operations."""
from __future__ import annotations
from pathlib import Path
import pytest
from EvoScientist.pm.crud.projects import create_project
from EvoScientist.pm.crud.tasks import create_task
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.crud.runs import (
    create_run, get_run, list_runs_for_task,
    update_run_status, update_run_output,
)
from EvoScientist.pm.db import create_schema

@pytest.fixture
def setup(tmp_path: Path):
    db = tmp_path / "test.db"
    create_schema(db)
    user = create_user(db, username="u1", password_hash="h")
    project = create_project(db, name="P1", created_by=user.id)
    task = create_task(db, project_id=project.id, title="Gel assay", created_by=user.id)
    return db, user, project, task

def test_create_and_get_run(setup):
    db, user, _, task = setup
    run = create_run(db, task_id=task.id, project_id=task.project_id,
                     agent_type="research", prompt="Find gel protocols", created_by=user.id)
    assert run.id is not None
    assert run.status == "pending"
    assert run.agent_type == "research"
    fetched = get_run(db, run.id)
    assert fetched is not None
    assert fetched.prompt == "Find gel protocols"

def test_list_runs_for_task(setup):
    db, user, _, task = setup
    create_run(db, task.id, task.project_id, "research", "p1", user.id)
    create_run(db, task.id, task.project_id, "code", "p2", user.id)
    runs = list_runs_for_task(db, task.id)
    assert len(runs) == 2
    assert {r.agent_type for r in runs} == {"research", "code"}

def test_update_run_status(setup):
    db, user, _, task = setup
    run = create_run(db, task.id, task.project_id, "research", "p", user.id)
    update_run_status(db, run.id, "running")
    fetched = get_run(db, run.id)
    assert fetched.status == "running"
    assert fetched.started_at is not None


def test_update_run_status_terminal_sets_finished_at(setup):
    db, user, _, task = setup
    run = create_run(db, task.id, task.project_id, "research", "p", user.id)
    update_run_status(db, run.id, "cancelled")
    fetched = get_run(db, run.id)
    assert fetched.status == "cancelled"
    assert fetched.finished_at is not None


def test_update_run_status_missing_raises(setup):
    db, *_ = setup
    with pytest.raises(ValueError, match="not found"):
        update_run_status(db, "nonexistent", "running")


def test_update_run_output_missing_raises(setup):
    db, *_ = setup
    with pytest.raises(ValueError, match="not found"):
        update_run_output(db, "nonexistent", "done", "output")

def test_update_run_output(setup):
    db, user, _, task = setup
    run = create_run(db, task.id, task.project_id, "research", "p", user.id)
    update_run_output(db, run.id, "done", "Found 3 protocols.")
    fetched = get_run(db, run.id)
    assert fetched.status == "done"
    assert fetched.output == "Found 3 protocols."
    assert fetched.finished_at is not None

def test_get_run_missing(setup):
    db, *_ = setup
    assert get_run(db, "nonexistent") is None
