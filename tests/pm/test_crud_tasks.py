"""Tests for task and comment CRUD."""
from __future__ import annotations

from pathlib import Path

import pytest

from EvoScientist.pm.crud.projects import create_project
from EvoScientist.pm.crud.tasks import (
    create_comment,
    create_task,
    delete_comment,
    delete_task,
    get_task,
    list_comments,
    list_tasks,
    update_task,
)
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.db import create_schema


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    return db_path


@pytest.fixture
def setup(db: Path):
    user = create_user(db, username="u1", password_hash="h")
    project = create_project(db, name="TestProject", created_by=user.id)
    return db, user, project


def test_create_and_get_task(setup) -> None:
    db, user, project = setup
    task = create_task(db, project_id=project.id, title="Write paper", created_by=user.id)
    assert task.id is not None
    assert task.status == "todo"
    assert task.priority == "medium"

    fetched = get_task(db, task.id)
    assert fetched is not None
    assert fetched.title == "Write paper"


def test_create_task_with_all_fields(setup) -> None:
    db, user, project = setup
    task = create_task(
        db,
        project_id=project.id,
        title="Run experiment",
        created_by=user.id,
        description="Train baseline model",
        assignee_id=user.id,
        priority="high",
        deadline="2026-05-01",
        session_id="abc123",
    )
    assert task.priority == "high"
    assert task.deadline == "2026-05-01"
    assert task.session_id == "abc123"


def test_list_tasks_filter_by_status(setup) -> None:
    db, user, project = setup
    create_task(db, project_id=project.id, title="T1", created_by=user.id)
    t2 = create_task(db, project_id=project.id, title="T2", created_by=user.id)
    update_task(db, t2.id, status="in_progress")

    todo = list_tasks(db, project_id=project.id, status="todo")
    in_prog = list_tasks(db, project_id=project.id, status="in_progress")
    assert len(todo) == 1
    assert len(in_prog) == 1


def test_update_task(setup) -> None:
    db, user, project = setup
    task = create_task(db, project_id=project.id, title="Draft", created_by=user.id)
    updated = update_task(db, task.id, title="Final Draft", status="done", priority="low")
    assert updated.title == "Final Draft"
    assert updated.status == "done"
    assert updated.priority == "low"


def test_delete_task(setup) -> None:
    db, user, project = setup
    task = create_task(db, project_id=project.id, title="Temp", created_by=user.id)
    assert delete_task(db, task.id) is True
    assert get_task(db, task.id) is None


def test_create_and_list_comments(setup) -> None:
    db, user, project = setup
    task = create_task(db, project_id=project.id, title="T", created_by=user.id)
    c1 = create_comment(db, task_id=task.id, body="First comment", author_id=user.id)
    c2 = create_comment(db, task_id=task.id, body="Second comment", author_id=user.id)

    comments = list_comments(db, task.id)
    assert len(comments) == 2
    assert comments[0].body == "First comment"
    assert comments[1].body == "Second comment"


def test_delete_comment(setup) -> None:
    db, user, project = setup
    task = create_task(db, project_id=project.id, title="T", created_by=user.id)
    comment = create_comment(db, task_id=task.id, body="Delete me", author_id=user.id)
    assert delete_comment(db, comment.id) is True
    assert list_comments(db, task.id) == []
