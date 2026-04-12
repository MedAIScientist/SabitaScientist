"""Tests for Experiment CRUD operations."""
from __future__ import annotations
from pathlib import Path
import pytest
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.crud.projects import create_project
from EvoScientist.pm.crud.tasks import create_task
from EvoScientist.pm.crud.experiments import (
    create_experiment, get_experiment, list_experiments,
    update_experiment, delete_experiment,
    link_task, unlink_task, list_linked_tasks,
)
from EvoScientist.pm.db import create_schema


@pytest.fixture
def setup(tmp_path: Path):
    db = tmp_path / "test.db"
    create_schema(db)
    user = create_user(db, username="u1", password_hash="h")
    project = create_project(db, name="CRISPR Project", created_by=user.id)
    task = create_task(db, project_id=project.id, title="Gel assay", created_by=user.id)
    return db, user, project, task


def test_create_and_get_experiment(setup):
    db, user, project, _ = setup
    exp = create_experiment(
        db, project_id=project.id, name="Western Blot #1",
        created_by=user.id, hypothesis="Protein X is expressed",
        tags=["blot", "protein"],
    )
    assert exp.id is not None
    assert exp.status == "planned"
    assert exp.tags == ["blot", "protein"]
    fetched = get_experiment(db, exp.id)
    assert fetched is not None
    assert fetched.name == "Western Blot #1"
    assert fetched.hypothesis == "Protein X is expressed"


def test_list_experiments(setup):
    db, user, project, _ = setup
    create_experiment(db, project_id=project.id, name="Exp A", created_by=user.id)
    create_experiment(db, project_id=project.id, name="Exp B", created_by=user.id)
    exps = list_experiments(db, project.id)
    assert len(exps) == 2
    assert {e.name for e in exps} == {"Exp A", "Exp B"}


def test_update_experiment(setup):
    db, user, project, _ = setup
    exp = create_experiment(db, project_id=project.id, name="Exp", created_by=user.id)
    updated = update_experiment(db, exp.id, name="Exp Renamed", status="running", tags=["x"])
    assert updated.name == "Exp Renamed"
    assert updated.status == "running"
    assert updated.tags == ["x"]


def test_delete_experiment(setup):
    db, user, project, _ = setup
    exp = create_experiment(db, project_id=project.id, name="Exp", created_by=user.id)
    assert delete_experiment(db, exp.id) is True
    assert get_experiment(db, exp.id) is None


def test_link_and_unlink_task(setup):
    db, user, project, task = setup
    exp = create_experiment(db, project_id=project.id, name="Exp", created_by=user.id)
    link_task(db, exp.id, task.id, linked_by=user.id)
    linked = list_linked_tasks(db, exp.id)
    assert len(linked) == 1
    assert linked[0].id == task.id
    unlink_task(db, exp.id, task.id)
    assert list_linked_tasks(db, exp.id) == []


def test_link_task_duplicate_raises(setup):
    db, user, project, task = setup
    exp = create_experiment(db, project_id=project.id, name="Exp", created_by=user.id)
    link_task(db, exp.id, task.id, linked_by=user.id)
    with pytest.raises(ValueError, match="already linked"):
        link_task(db, exp.id, task.id, linked_by=user.id)


def test_get_experiment_missing(setup):
    db, *_ = setup
    assert get_experiment(db, "nonexistent") is None
