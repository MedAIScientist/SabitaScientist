"""Tests for attachment upload/download/delete API endpoints."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.users import create_user


@pytest.fixture
def auth_client(tmp_db: Path):
    """Return a TestClient with a valid auth token and project/experiment/entry IDs."""
    tc = TestClient(create_app(tmp_db), raise_server_exceptions=True)

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
