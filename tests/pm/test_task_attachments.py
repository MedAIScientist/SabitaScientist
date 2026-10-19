"""Task attachments: a task's files, next to the task.

An attachment has exactly one owner — an experiment entry or a task. These tests pin
the task half of that contract, and the sharing that makes it worth generalising the
table instead of adding a second one: the same upload validation, the same presigned
download, the same delete.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gazzali.api.app import create_app
from gazzali.auth import hash_password
from gazzali.crud.users import create_user


@pytest.fixture(autouse=True)
def _object_storage(monkeypatch):
    """The suite runs without S3, so stand in for the three calls the routes make."""
    from gazzali.api.routes import attachments as module

    monkeypatch.setattr(module, "upload_file", lambda *a, **k: "stored-key")
    monkeypatch.setattr(
        module, "generate_presigned_url", lambda key, expires=3600: f"http://garage/{key}"
    )
    monkeypatch.setattr(module, "delete_object", lambda key: None)
    # Serving the bytes back goes through the store as well.
    monkeypatch.setattr(module, "get_object_stream", lambda key: BytesIO(b"a,b\n1,2\n"))


@pytest.fixture
def client(tmp_db: Path) -> TestClient:
    create_user(tmp_db, "admin", hash_password("pw"), is_admin=True, role="admin")
    c = TestClient(create_app(tmp_db))
    token = c.post("/api/v1/auth/login", json={"username": "admin", "password": "pw"}).json()["token"]
    c.token = token
    return c


def _h(client) -> dict:
    return {"Authorization": f"Bearer {client.token}"}


def _project_and_task(client) -> tuple[str, str]:
    pid = client.post("/api/v1/projects", json={"name": "Imaging"}, headers=_h(client)).json()["id"]
    phase = client.post(
        f"/api/v1/projects/{pid}/phases", json={"name": "Analysis", "position": 0}, headers=_h(client)
    ).json()["id"]
    task = client.post(
        f"/api/v1/projects/{pid}/tasks",
        json={"title": "Denoise", "phase_id": phase},
        headers=_h(client),
    ).json()["id"]
    return pid, task


def _upload(client, pid: str, task: str, name: str = "cohort.csv", content: bytes = b"a,b\n1,2\n",
            content_type: str = "text/csv"):
    return client.post(
        f"/api/v1/projects/{pid}/tasks/{task}/attachments",
        files={"file": (name, BytesIO(content), content_type)},
        headers=_h(client),
    )


# ── Uploading and listing ────────────────────────────────────────────────────


def test_a_file_can_be_attached_to_a_task_and_listed_back(client) -> None:
    pid, task = _project_and_task(client)

    created = _upload(client, pid, task)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["task_id"] == task
    assert body["entry_id"] is None
    assert body["filename"] == "cohort.csv"
    assert body["size_bytes"] == 8
    assert body["download_url"]

    listed = client.get(f"/api/v1/projects/{pid}/tasks/{task}/attachments", headers=_h(client))
    assert listed.status_code == 200, listed.text
    assert [a["filename"] for a in listed.json()] == ["cohort.csv"]


def test_several_files_keep_their_order(client) -> None:
    pid, task = _project_and_task(client)
    for name in ("first.txt", "second.txt", "third.txt"):
        assert _upload(client, pid, task, name=name, content_type="text/plain").status_code == 201

    listed = client.get(f"/api/v1/projects/{pid}/tasks/{task}/attachments", headers=_h(client)).json()
    assert [a["filename"] for a in listed] == ["first.txt", "second.txt", "third.txt"]


def test_a_task_with_no_files_lists_empty(client) -> None:
    pid, task = _project_and_task(client)
    listed = client.get(f"/api/v1/projects/{pid}/tasks/{task}/attachments", headers=_h(client))
    assert listed.status_code == 200
    assert listed.json() == []


def test_an_image_is_accepted_and_a_binary_is_not(client) -> None:
    """The allow-list is shared with entry attachments, so it applies here too."""
    pid, task = _project_and_task(client)
    assert _upload(client, pid, task, "scan.png", b"\x89PNG", "image/png").status_code == 201

    rejected = _upload(client, pid, task, "app.exe", b"MZ", "application/x-msdownload")
    assert rejected.status_code == 415
    assert "not allowed" in rejected.json()["detail"]


def test_an_oversized_file_is_refused(client, monkeypatch) -> None:
    from gazzali.api.routes import attachments as module

    monkeypatch.setattr(module, "_MAX_BYTES", 4)
    pid, task = _project_and_task(client)

    too_big = _upload(client, pid, task, "big.txt", b"12345", "text/plain")
    assert too_big.status_code == 413
    listed = client.get(f"/api/v1/projects/{pid}/tasks/{task}/attachments", headers=_h(client)).json()
    assert listed == [], "a refused upload must not leave a record"


# ── Scoping: the task must be in the project in the URL ──────────────────────


def test_a_task_from_another_project_is_not_reachable_through_this_project(client) -> None:
    _pid, task = _project_and_task(client)
    other = client.post("/api/v1/projects", json={"name": "Other"}, headers=_h(client)).json()["id"]

    assert _upload(client, other, task).status_code == 404
    assert client.get(
        f"/api/v1/projects/{other}/tasks/{task}/attachments", headers=_h(client)
    ).status_code == 404


def test_an_unknown_task_is_refused(client) -> None:
    pid, _task = _project_and_task(client)
    assert _upload(client, pid, "no-such-task").status_code == 404


# ── Downloading and deleting work through the shared endpoints ───────────────


def test_a_task_attachment_downloads_through_the_shared_endpoint(client) -> None:
    pid, task = _project_and_task(client)
    attachment = _upload(client, pid, task).json()["id"]

    resp = client.get(
        f"/api/v1/attachments/{attachment}/download", headers=_h(client), follow_redirects=False
    )
    assert resp.status_code == 302
    assert resp.headers["location"]


def test_the_file_can_be_served_back_through_the_api(client) -> None:
    """Presigned URLs need a publicly reachable bucket; this deployment has none, so
    the bytes are served from the API origin the browser already talks to."""
    pid, task = _project_and_task(client)
    attachment = _upload(client, pid, task).json()["id"]

    resp = client.get(f"/api/v1/attachments/{attachment}/content", headers=_h(client))
    assert resp.status_code == 200, resp.text
    assert resp.content == b"a,b\n1,2\n"
    assert resp.headers["content-type"].startswith("text/csv")
    # Inline, so the browser can show an image or a PDF instead of only saving it.
    assert resp.headers["content-disposition"].startswith("inline")


def test_serving_a_file_needs_authentication(client) -> None:
    pid, task = _project_and_task(client)
    attachment = _upload(client, pid, task).json()["id"]
    assert client.get(f"/api/v1/attachments/{attachment}/content").status_code == 401


def test_a_raw_phi_file_is_never_served(client, tmp_db) -> None:
    """The classification rule must hold on the new path as well as the redirect."""
    import sqlite3

    from gazzali.db import get_db_path

    pid, task = _project_and_task(client)
    attachment = _upload(client, pid, task).json()["id"]
    conn = sqlite3.connect(str(get_db_path()))
    conn.execute("UPDATE attachments SET classification = 'raw_phi' WHERE id = ?", (attachment,))
    conn.commit()
    conn.close()

    assert client.get(f"/api/v1/attachments/{attachment}/content", headers=_h(client)).status_code == 403
    assert client.get(
        f"/api/v1/attachments/{attachment}/download", headers=_h(client), follow_redirects=False
    ).status_code == 403


def test_a_task_attachment_can_be_deleted(client) -> None:
    pid, task = _project_and_task(client)
    attachment = _upload(client, pid, task).json()["id"]

    assert client.delete(f"/api/v1/attachments/{attachment}", headers=_h(client)).status_code == 204
    assert client.get(f"/api/v1/projects/{pid}/tasks/{task}/attachments", headers=_h(client)).json() == []


def test_deleting_a_task_deletes_its_attachments(client) -> None:
    """The files belong to the task: an orphaned row would keep a deleted task's data."""
    import sqlite3

    from gazzali.db import get_db_path

    pid, task = _project_and_task(client)
    attachment = _upload(client, pid, task).json()["id"]

    assert client.delete(f"/api/v1/projects/{pid}/tasks/{task}", headers=_h(client)).status_code in (200, 204)

    conn = sqlite3.connect(str(get_db_path()))
    left = conn.execute("SELECT COUNT(*) FROM attachments WHERE id = ?", (attachment,)).fetchone()[0]
    conn.close()
    assert left == 0


# ── One owner, never two ────────────────────────────────────────────────────


def test_entry_attachments_still_work(client) -> None:
    """Generalising the table must not disturb the owner that already existed."""
    pid = client.post("/api/v1/projects", json={"name": "P"}, headers=_h(client)).json()["id"]
    exp = client.post(
        f"/api/v1/projects/{pid}/experiments", json={"name": "Exp"}, headers=_h(client)
    ).json()["id"]
    entry = client.post(
        f"/api/v1/projects/{pid}/experiments/{exp}/entries",
        json={"type": "note", "title": "Note"}, headers=_h(client),
    ).json()["id"]

    created = client.post(
        f"/api/v1/projects/{pid}/experiments/{exp}/entries/{entry}/attachments",
        files={"file": ("note.txt", BytesIO(b"hi"), "text/plain")},
        headers=_h(client),
    )
    assert created.status_code == 201, created.text
    assert created.json()["entry_id"] == entry
    assert created.json()["task_id"] is None


# ── The project-wide view ────────────────────────────────────────────────────


def _entry_with_attachment(client, pid: str, name: str = "figure.png") -> str:
    exp = client.post(
        f"/api/v1/projects/{pid}/experiments", json={"name": "Exp"}, headers=_h(client)
    ).json()["id"]
    entry = client.post(
        f"/api/v1/projects/{pid}/experiments/{exp}/entries",
        json={"type": "result", "title": "Final run"}, headers=_h(client),
    ).json()["id"]
    created = client.post(
        f"/api/v1/projects/{pid}/experiments/{exp}/entries/{entry}/attachments",
        files={"file": (name, BytesIO(b"\x89PNG"), "image/png")},
        headers=_h(client),
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_the_project_view_shows_task_and_entry_files_together(client) -> None:
    """A file is found by looking in the project, not by guessing where it was attached."""
    pid, task = _project_and_task(client)
    task_file = _upload(client, pid, task, "cohort.csv").json()["id"]
    entry_file = _entry_with_attachment(client, pid)

    listed = client.get(f"/api/v1/projects/{pid}/attachments", headers=_h(client))
    assert listed.status_code == 200, listed.text
    rows = {row["id"]: row for row in listed.json()}
    assert set(rows) == {task_file, entry_file}

    assert rows[task_file]["owner_kind"] == "task"
    assert rows[task_file]["owner_title"] == "Denoise"
    assert rows[task_file]["experiment_id"] is None

    assert rows[entry_file]["owner_kind"] == "entry"
    assert rows[entry_file]["owner_title"] == "Final run"
    assert rows[entry_file]["experiment_id"]


def test_the_project_view_never_leaks_another_projects_files(client) -> None:
    pid, task = _project_and_task(client)
    _upload(client, pid, task, "mine.csv")

    other = client.post("/api/v1/projects", json={"name": "Other"}, headers=_h(client)).json()["id"]
    other_task = client.post(
        f"/api/v1/projects/{other}/tasks", json={"title": "Theirs"}, headers=_h(client)
    ).json()["id"]
    _upload(client, other, other_task, "theirs.csv")

    listed = client.get(f"/api/v1/projects/{pid}/attachments", headers=_h(client)).json()
    assert [row["filename"] for row in listed] == ["mine.csv"]


def test_the_project_view_can_be_filtered_by_owner_kind(client) -> None:
    pid, task = _project_and_task(client)
    _upload(client, pid, task, "task-file.csv")
    _entry_with_attachment(client, pid, "entry-file.png")

    only_tasks = client.get(f"/api/v1/projects/{pid}/attachments?kind=task", headers=_h(client)).json()
    assert [r["filename"] for r in only_tasks] == ["task-file.csv"]

    only_entries = client.get(f"/api/v1/projects/{pid}/attachments?kind=entry", headers=_h(client)).json()
    assert [r["filename"] for r in only_entries] == ["entry-file.png"]


def test_the_project_view_names_the_uploader(client) -> None:
    pid, task = _project_and_task(client)
    _upload(client, pid, task)
    row = client.get(f"/api/v1/projects/{pid}/attachments", headers=_h(client)).json()[0]
    assert row["uploader_name"] == "admin"


def test_a_non_member_cannot_list_the_projects_files(client, tmp_db) -> None:
    from gazzali.auth import hash_password
    from gazzali.crud.users import create_user

    pid, task = _project_and_task(client)
    _upload(client, pid, task)

    create_user(tmp_db, "outsider", hash_password("pw"), role="student")
    outsider = client.post("/api/v1/auth/login", json={"username": "outsider", "password": "pw"}).json()["token"]
    resp = client.get(
        f"/api/v1/projects/{pid}/attachments", headers={"Authorization": f"Bearer {outsider}"}
    )
    # 404 rather than 403: a non-member should not learn the project exists.
    assert resp.status_code == 404


def test_only_a_member_can_delete_or_reclassify_a_file(client, tmp_db) -> None:
    """Knowing an attachment id must not be enough to touch another project's file."""
    from gazzali.auth import hash_password
    from gazzali.crud.users import create_user

    pid, task = _project_and_task(client)
    attachment = _upload(client, pid, task).json()["id"]

    create_user(tmp_db, "outsider", hash_password("pw"), role="student")
    outsider_token = client.post(
        "/api/v1/auth/login", json={"username": "outsider", "password": "pw"}
    ).json()["token"]
    outsider = {"Authorization": f"Bearer {outsider_token}"}

    assert client.get(f"/api/v1/attachments/{attachment}/content", headers=outsider).status_code == 404
    assert client.get(
        f"/api/v1/attachments/{attachment}/download", headers=outsider, follow_redirects=False
    ).status_code == 404
    assert client.put(
        f"/api/v1/attachments/{attachment}/classify", json={"classification": "public"}, headers=outsider
    ).status_code == 404
    assert client.delete(f"/api/v1/attachments/{attachment}", headers=outsider).status_code == 404

    # …and the file is still there for the member who owns it.
    assert client.get(
        f"/api/v1/projects/{pid}/tasks/{task}/attachments", headers=_h(client)
    ).json() != []


def test_an_attachment_must_have_exactly_one_owner(tmp_db) -> None:
    from gazzali.crud.attachments import create_attachment
    from gazzali.db import get_db

    with get_db(tmp_db) as db, pytest.raises(ValueError, match="exactly one owner"):
        create_attachment(db, None, "x.txt", "k", "text/plain", 1)  # no owner at all

    with get_db(tmp_db) as db, pytest.raises(ValueError, match="exactly one owner"):
        create_attachment(db, "entry", "x.txt", "k", "text/plain", 1, task_id="task")  # two owners
