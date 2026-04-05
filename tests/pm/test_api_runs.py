# tests/pm/test_api_runs.py
"""Tests for PM run API endpoints."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import AsyncMock, patch
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
    import EvoScientist.pm.crud.runs as runs_mod
    import EvoScientist.pm.api.routes.auth as auth_r
    import EvoScientist.pm.api.routes.users as users_r
    import EvoScientist.pm.api.routes.projects as proj_r
    import EvoScientist.pm.api.routes.tasks as tasks_r
    import EvoScientist.pm.api.routes.runs as runs_r
    for mod in [deps_mod, users_mod, proj_mod, tasks_mod, runs_mod,
                auth_r, users_r, proj_r, tasks_r, runs_r]:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda: tmp_db
    return create_app(tmp_db)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def member_token(tmp_db, client):
    create_user(tmp_db, username="lab", password_hash=hash_password("pass"))
    resp = client.post("/api/v1/auth/login", json={"username": "lab", "password": "pass"})
    return resp.json()["token"]


@pytest.fixture
def project_task(tmp_db, member_token, client):
    headers = {"Authorization": f"Bearer {member_token}"}
    proj = client.post("/api/v1/projects", json={"name": "CRISPR"}, headers=headers).json()
    task = client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Gel assay"},
        headers=headers,
    ).json()
    return proj["id"], task["id"]


def test_create_run_returns_201(client, member_token, project_task):
    project_id, task_id = project_task
    with patch("EvoScientist.pm.api.routes.runs._notify_runner", new=AsyncMock()):
        resp = client.post(
            f"/api/v1/projects/{project_id}/tasks/{task_id}/runs",
            json={"agent_type": "research", "prompt": "Find gel protocols"},
            headers={"Authorization": f"Bearer {member_token}"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["agent_type"] == "research"
    assert data["task_id"] == task_id


def test_list_runs_returns_empty_initially(client, member_token, project_task):
    project_id, task_id = project_task
    resp = client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/runs",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_runs_returns_created_runs(client, member_token, project_task):
    project_id, task_id = project_task
    headers = {"Authorization": f"Bearer {member_token}"}
    with patch("EvoScientist.pm.api.routes.runs._notify_runner", new=AsyncMock()):
        client.post(
            f"/api/v1/projects/{project_id}/tasks/{task_id}/runs",
            json={"agent_type": "research", "prompt": "p1"},
            headers=headers,
        )
    resp = client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/runs",
        headers=headers,
    )
    assert len(resp.json()) == 1


def test_create_run_requires_auth(client, project_task):
    project_id, task_id = project_task
    resp = client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/runs",
        json={"agent_type": "research", "prompt": "p"},
    )
    assert resp.status_code == 401
