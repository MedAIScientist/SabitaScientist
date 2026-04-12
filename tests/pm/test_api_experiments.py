"""Tests for Experiment API routes."""
from __future__ import annotations
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.crud.projects import create_project
from EvoScientist.pm.crud.tasks import create_task
from EvoScientist.pm.db import create_schema


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db = tmp_path / "test.db"
    create_schema(db)
    return db


@pytest.fixture
def app(tmp_db: Path):
    import EvoScientist.pm.api.deps as deps_mod
    import EvoScientist.pm.crud.users as users_mod
    import EvoScientist.pm.crud.projects as proj_mod
    import EvoScientist.pm.crud.tasks as tasks_mod
    import EvoScientist.pm.crud.experiments as exps_mod
    import EvoScientist.pm.crud.experiment_entries as entries_mod
    import EvoScientist.pm.api.routes.auth as auth_r
    import EvoScientist.pm.api.routes.users as users_r
    import EvoScientist.pm.api.routes.projects as proj_r
    import EvoScientist.pm.api.routes.tasks as tasks_r
    import EvoScientist.pm.api.routes.runs as runs_r
    import EvoScientist.pm.api.routes.experiments as exps_r
    for mod in [deps_mod, users_mod, proj_mod, tasks_mod, exps_mod, entries_mod,
                auth_r, users_r, proj_r, tasks_r, runs_r, exps_r]:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda: tmp_db
    return create_app(tmp_db)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def owner_token(tmp_db, client):
    create_user(tmp_db, username="owner", password_hash=hash_password("pass"))
    resp = client.post("/api/v1/auth/login", json={"username": "owner", "password": "pass"})
    return resp.json()["token"]


@pytest.fixture
def project_and_task(tmp_db, owner_token, client):
    headers = {"Authorization": f"Bearer {owner_token}"}
    proj = client.post("/api/v1/projects", json={"name": "CRISPR"}, headers=headers).json()
    task = client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Gel assay"}, headers=headers,
    ).json()
    return proj["id"], task["id"]


def test_create_experiment_returns_201(client, owner_token, project_and_task):
    project_id, _ = project_and_task
    resp = client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Western Blot #1", "tags": ["blot"], "status": "planned"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Western Blot #1"
    assert data["tags"] == ["blot"]
    assert data["status"] == "planned"


def test_list_experiments_empty(client, owner_token, project_and_task):
    project_id, _ = project_and_task
    resp = client.get(
        f"/api/v1/projects/{project_id}/experiments",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_experiments_returns_created(client, owner_token, project_and_task):
    project_id, _ = project_and_task
    headers = {"Authorization": f"Bearer {owner_token}"}
    client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Exp A"}, headers=headers,
    )
    resp = client.get(f"/api/v1/projects/{project_id}/experiments", headers=headers)
    assert len(resp.json()) == 1


def test_create_entry(client, owner_token, project_and_task):
    project_id, _ = project_and_task
    headers = {"Authorization": f"Bearer {owner_token}"}
    exp = client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Exp"}, headers=headers,
    ).json()
    resp = client.post(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/entries",
        json={"type": "note", "title": "Day 1", "body": "All good"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Day 1"
    assert resp.json()["type"] == "note"


def test_list_entries_with_type_filter(client, owner_token, project_and_task):
    project_id, _ = project_and_task
    headers = {"Authorization": f"Bearer {owner_token}"}
    exp = client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Exp"}, headers=headers,
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/entries",
        json={"type": "note", "title": "N1"}, headers=headers,
    )
    client.post(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/entries",
        json={"type": "result", "title": "R1"}, headers=headers,
    )
    resp = client.get(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/entries?type=note",
        headers=headers,
    )
    assert len(resp.json()) == 1
    assert resp.json()[0]["type"] == "note"


def test_link_task(client, owner_token, project_and_task):
    project_id, task_id = project_and_task
    headers = {"Authorization": f"Bearer {owner_token}"}
    exp = client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Exp"}, headers=headers,
    ).json()
    resp = client.post(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/tasks",
        json={"task_id": task_id}, headers=headers,
    )
    assert resp.status_code == 201
    linked = client.get(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/tasks",
        headers=headers,
    ).json()
    assert len(linked) == 1
    assert linked[0]["id"] == task_id


def test_requires_auth(client, project_and_task):
    project_id, _ = project_and_task
    resp = client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Exp"},
    )
    assert resp.status_code == 401
