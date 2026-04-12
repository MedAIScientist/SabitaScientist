"""Tests for attachment upload/download/delete API endpoints."""
from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.db import create_schema


def _make_app(tmp_db: Path) -> TestClient:
    """Create an app with all get_db_path / get_db calls redirected to tmp_db."""
    import EvoScientist.pm.api.deps as deps_mod
    import EvoScientist.pm.api.routes.attachments as att_r
    import EvoScientist.pm.api.routes.auth as auth_r
    import EvoScientist.pm.api.routes.experiments as exps_r
    import EvoScientist.pm.api.routes.projects as proj_r
    import EvoScientist.pm.api.routes.runs as runs_r
    import EvoScientist.pm.api.routes.tasks as tasks_r
    import EvoScientist.pm.api.routes.users as users_r
    import EvoScientist.pm.crud.experiment_entries as entries_mod
    import EvoScientist.pm.crud.experiments as exps_mod
    import EvoScientist.pm.crud.projects as proj_mod
    import EvoScientist.pm.crud.tasks as tasks_mod
    import EvoScientist.pm.crud.users as users_mod
    from EvoScientist.pm.db import get_db as _real_get_db

    for mod in [
        deps_mod, users_mod, proj_mod, tasks_mod, exps_mod, entries_mod,
        auth_r, users_r, proj_r, tasks_r, runs_r, exps_r, att_r,
    ]:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda _db=tmp_db: _db

    # Patch get_db in the attachments routes module so it always uses the temp DB
    att_r.get_db = lambda: _real_get_db(tmp_db)

    return create_app(tmp_db)


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    return db_path


@pytest.fixture
def auth_client(tmp_db: Path):
    """Return a TestClient with a valid auth token and project/experiment/entry IDs."""
    app = _make_app(tmp_db)
    tc = TestClient(app, raise_server_exceptions=True)

    # Create user via CRUD and log in via API to get a real token
    create_user(tmp_db, username="alice", password_hash=hash_password("pass123"), is_admin=True)
    login_resp = tc.post("/api/v1/auth/login", json={"username": "alice", "password": "pass123"})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["token"]

    headers = {"Authorization": f"Bearer {token}"}
    tc.headers.update(headers)

    # Create project via API
    proj_resp = tc.post("/api/v1/projects", json={"name": "P"}, headers=headers)
    assert proj_resp.status_code == 201, proj_resp.text
    pid = proj_resp.json()["id"]

    # Create experiment via API
    exp_resp = tc.post(
        f"/api/v1/projects/{pid}/experiments",
        json={"name": "Exp", "status": "planned", "tags": []},
        headers=headers,
    )
    assert exp_resp.status_code == 201, exp_resp.text
    eid = exp_resp.json()["id"]

    # Create entry via API
    entry_resp = tc.post(
        f"/api/v1/projects/{pid}/experiments/{eid}/entries",
        json={"type": "note", "title": "N", "body": ""},
        headers=headers,
    )
    assert entry_resp.status_code == 201, entry_resp.text
    enid = entry_resp.json()["id"]

    return tc, pid, eid, enid


UPLOAD_URL = "/api/v1/projects/{pid}/experiments/{eid}/entries/{enid}/attachments"


def test_list_attachments_empty(auth_client):
    tc, pid, eid, enid = auth_client
    resp = tc.get(UPLOAD_URL.format(pid=pid, eid=eid, enid=enid))
    assert resp.status_code == 200
    assert resp.json() == []


def test_upload_attachment(auth_client):
    tc, pid, eid, enid = auth_client
    with patch("EvoScientist.pm.api.routes.attachments.upload_file") as mock_upload, \
         patch("EvoScientist.pm.api.routes.attachments.generate_presigned_url") as mock_url:
        mock_upload.return_value = "entries/en1/uuid/test.txt"
        mock_url.return_value = "http://garage/presigned/test.txt"

        resp = tc.post(
            UPLOAD_URL.format(pid=pid, eid=eid, enid=enid),
            files={"file": ("test.txt", BytesIO(b"hello world"), "text/plain")},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["filename"] == "test.txt"
    assert data["content_type"] == "text/plain"
    assert data["size_bytes"] == 11
    assert data["download_url"] == "http://garage/presigned/test.txt"
    assert data["entry_id"] == enid


def test_upload_attachment_type_rejected(auth_client):
    tc, pid, eid, enid = auth_client
    resp = tc.post(
        UPLOAD_URL.format(pid=pid, eid=eid, enid=enid),
        files={"file": ("evil.exe", BytesIO(b"MZ"), "application/x-msdownload")},
    )
    assert resp.status_code == 415


def test_upload_attachment_too_large(auth_client):
    tc, pid, eid, enid = auth_client
    with patch("EvoScientist.pm.api.routes.attachments._MAX_BYTES", 1):
        resp = tc.post(
            UPLOAD_URL.format(pid=pid, eid=eid, enid=enid),
            files={"file": ("big.txt", BytesIO(b"x" * 2), "text/plain")},
        )
    assert resp.status_code == 413


def test_delete_attachment(auth_client):
    tc, pid, eid, enid = auth_client
    with patch("EvoScientist.pm.api.routes.attachments.upload_file") as mu, \
         patch("EvoScientist.pm.api.routes.attachments.generate_presigned_url") as mg:
        mu.return_value = "k"
        mg.return_value = "http://x"
        upload_resp = tc.post(
            UPLOAD_URL.format(pid=pid, eid=eid, enid=enid),
            files={"file": ("del.txt", BytesIO(b"bye"), "text/plain")},
        )
    assert upload_resp.status_code == 201, upload_resp.text
    att_id = upload_resp.json()["id"]

    with patch("EvoScientist.pm.api.routes.attachments.delete_object"):
        del_resp = tc.delete(f"/api/v1/attachments/{att_id}")
    assert del_resp.status_code == 204

    # Confirm deleted from list
    with patch("EvoScientist.pm.api.routes.attachments.generate_presigned_url", return_value="http://x"):
        list_resp = tc.get(UPLOAD_URL.format(pid=pid, eid=eid, enid=enid))
    assert list_resp.json() == []
