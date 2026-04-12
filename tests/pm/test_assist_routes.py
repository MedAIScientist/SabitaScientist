"""Tests for experiment assist API endpoints."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import bcrypt
import pytest
from fastapi.testclient import TestClient

from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.db import create_schema


@pytest.fixture
def auth_client(tmp_path: Path):
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    # Patch get_db_path in all relevant modules before creating the app
    import EvoScientist.pm.api.deps as deps_mod
    import EvoScientist.pm.api.routes.assists as assists_mod
    import EvoScientist.pm.api.routes.auth as auth_r
    import EvoScientist.pm.api.routes.experiments as exp_r
    import EvoScientist.pm.api.routes.projects as proj_r
    import EvoScientist.pm.api.routes.runs as runs_r
    import EvoScientist.pm.api.routes.tasks as tasks_r
    import EvoScientist.pm.api.routes.users as users_r
    import EvoScientist.pm.crud.assists as assists_crud
    import EvoScientist.pm.crud.experiment_entries as entries_crud
    import EvoScientist.pm.crud.experiments as exp_crud
    import EvoScientist.pm.crud.projects as proj_crud
    import EvoScientist.pm.crud.tasks as tasks_crud
    import EvoScientist.pm.crud.users as users_crud

    for mod in [
        deps_mod, assists_mod, auth_r, exp_r, proj_r, runs_r, tasks_r, users_r,
        assists_crud, entries_crud, exp_crud, proj_crud, tasks_crud, users_crud,
    ]:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda: db_path

    app = create_app(db_path)

    now = datetime.now(timezone.utc).isoformat()
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    pw = bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?,?,?,?,?)",
        ("u1", "alice", pw, 1, now),
    )
    conn.execute(
        "INSERT INTO projects (id, name, created_by, created_at) VALUES (?,?,?,?)",
        ("p1", "P", "u1", now),
    )
    conn.execute(
        "INSERT INTO project_members (project_id, user_id, role, added_at) VALUES (?,?,?,?)",
        ("p1", "u1", "owner", now),
    )
    conn.execute(
        """INSERT INTO experiments (id, project_id, name, status, tags,
           created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
        ("e1", "p1", "Exp 1", "planned", '["ml"]', "u1", now, now),
    )
    conn.execute(
        "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?,?,?)",
        ("tok1", "u1", expires),
    )
    conn.commit()
    conn.close()

    tc = TestClient(app, raise_server_exceptions=True)
    tc.headers.update({"Authorization": "Bearer tok1"})
    return tc, db_path


ASSIST_URL = "/api/v1/projects/p1/experiments/e1/assist"
LIST_URL = "/api/v1/projects/p1/experiments/e1/assists"


def test_list_assists_empty(auth_client):
    tc, _ = auth_client
    resp = tc.get(LIST_URL)
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_assist(auth_client):
    tc, _ = auth_client
    with patch("EvoScientist.pm.api.routes.assists._notify_runner", new_callable=AsyncMock):
        resp = tc.post(ASSIST_URL, json={"prompt": "Write a hypothesis", "target_field": "hypothesis"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["prompt"] == "Write a hypothesis"
    assert data["target_field"] == "hypothesis"
    assert data["status"] == "pending"
    assert data["experiment_id"] == "e1"
    assert data["id"]


def test_context_includes_experiment_fields(auth_client):
    """Context snapshot assembled by POST must include experiment name."""
    tc, db_path = auth_client
    with patch("EvoScientist.pm.api.routes.assists._notify_runner", new_callable=AsyncMock):
        resp = tc.post(ASSIST_URL, json={"prompt": "Help"})
    assist_id = resp.json()["id"]

    # Read context_json from DB directly
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT context_json FROM experiment_assists WHERE id = ?", (assist_id,)
    ).fetchone()
    conn.close()
    ctx = json.loads(row[0])
    assert ctx["name"] == "Exp 1"
    assert "entries" in ctx
    assert "linked_tasks" in ctx


def test_create_assist_experiment_not_found(auth_client):
    tc, _ = auth_client
    with patch("EvoScientist.pm.api.routes.assists._notify_runner", new_callable=AsyncMock):
        resp = tc.post(
            "/api/v1/projects/p1/experiments/NOPE/assist",
            json={"prompt": "x"},
        )
    assert resp.status_code == 404


def test_create_assist_not_member(auth_client):
    tc, db_path = auth_client
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO projects (id, name, created_by, created_at) VALUES (?,?,?,?)",
        ("p2", "Other", "u1", now),
    )
    conn.execute(
        """INSERT INTO experiments (id, project_id, name, status, tags,
           created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
        ("e2", "p2", "Other Exp", "planned", "[]", "u1", now, now),
    )
    conn.commit()
    conn.close()
    with patch("EvoScientist.pm.api.routes.assists._notify_runner", new_callable=AsyncMock):
        resp = tc.post(
            "/api/v1/projects/p2/experiments/e2/assist",
            json={"prompt": "x"},
        )
    assert resp.status_code == 403


def test_cancel_assist(auth_client):
    tc, _ = auth_client
    with patch("EvoScientist.pm.api.routes.assists._notify_runner", new_callable=AsyncMock):
        create_resp = tc.post(ASSIST_URL, json={"prompt": "Help"})
    assist_id = create_resp.json()["id"]

    with patch("EvoScientist.pm.api.routes.assists.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.delete = AsyncMock()
        resp = tc.delete(f"/api/v1/assists/{assist_id}")
    assert resp.status_code == 204
