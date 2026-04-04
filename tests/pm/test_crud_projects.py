"""Tests for project and member CRUD."""
from __future__ import annotations

from pathlib import Path

import pytest

from EvoScientist.pm.crud.projects import (
    add_member,
    create_project,
    delete_project,
    get_member_role,
    get_project,
    list_projects_for_user,
    remove_member,
    update_member_role,
    update_project,
)
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.db import create_schema


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    return db_path


@pytest.fixture
def owner(db: Path):
    return create_user(db, username="owner", password_hash="h")


@pytest.fixture
def editor(db: Path):
    return create_user(db, username="editor", password_hash="h")


def test_create_and_get_project(db: Path, owner) -> None:
    project = create_project(db, name="Alpha", created_by=owner.id)
    assert project.id is not None
    assert project.name == "Alpha"

    fetched = get_project(db, project.id)
    assert fetched is not None
    assert fetched.name == "Alpha"


def test_get_project_missing(db: Path) -> None:
    assert get_project(db, "no-such-id") is None


def test_create_project_auto_adds_owner_member(db: Path, owner) -> None:
    project = create_project(db, name="Beta", created_by=owner.id)
    role = get_member_role(db, project.id, owner.id)
    assert role == "owner"


def test_list_projects_for_user(db: Path, owner, editor) -> None:
    p1 = create_project(db, name="P1", created_by=owner.id)
    p2 = create_project(db, name="P2", created_by=owner.id)
    add_member(db, project_id=p1.id, user_id=editor.id, role="editor")

    owner_projects = {p.id for p in list_projects_for_user(db, owner.id)}
    editor_projects = {p.id for p in list_projects_for_user(db, editor.id)}

    assert {p1.id, p2.id} == owner_projects
    assert editor_projects == {p1.id}


def test_add_and_remove_member(db: Path, owner, editor) -> None:
    project = create_project(db, name="Gamma", created_by=owner.id)
    add_member(db, project_id=project.id, user_id=editor.id, role="editor")
    assert get_member_role(db, project.id, editor.id) == "editor"

    remove_member(db, project_id=project.id, user_id=editor.id)
    assert get_member_role(db, project.id, editor.id) is None


def test_update_member_role(db: Path, owner, editor) -> None:
    project = create_project(db, name="Delta", created_by=owner.id)
    add_member(db, project_id=project.id, user_id=editor.id, role="editor")
    update_member_role(db, project_id=project.id, user_id=editor.id, role="viewer")
    assert get_member_role(db, project.id, editor.id) == "viewer"


def test_update_project(db: Path, owner) -> None:
    project = create_project(db, name="Epsilon", created_by=owner.id)
    updated = update_project(db, project.id, name="Epsilon v2", description="New desc")
    assert updated.name == "Epsilon v2"
    assert updated.description == "New desc"


def test_delete_project(db: Path, owner) -> None:
    project = create_project(db, name="Zeta", created_by=owner.id)
    assert delete_project(db, project.id) is True
    assert get_project(db, project.id) is None


def test_get_member_role_nonmember(db: Path, owner, editor) -> None:
    project = create_project(db, name="Eta", created_by=owner.id)
    assert get_member_role(db, project.id, editor.id) is None
