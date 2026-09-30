"""Tests for task and comment routes."""


def _make_project(client, token):
    resp = client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {token}"})
    return resp.json()["id"]


def test_create_and_list_tasks(client, admin_token) -> None:
    pid = _make_project(client, admin_token)
    client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T1"}, headers={"Authorization": f"Bearer {admin_token}"})
    client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T2", "priority": "high"}, headers={"Authorization": f"Bearer {admin_token}"})

    resp = client.get(f"/api/v1/projects/{pid}/tasks", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_task_status(client, admin_token) -> None:
    pid = _make_project(client, admin_token)
    task_id = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T"}, headers={"Authorization": f"Bearer {admin_token}"}).json()["id"]

    resp = client.put(f"/api/v1/projects/{pid}/tasks/{task_id}", json={"status": "done"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


def test_viewer_cannot_create_task(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.projects import add_member
    from EvoScientist.pm.crud.users import create_user

    viewer = create_user(tmp_db, username="v2", password_hash=hash_password("p"))
    pid = _make_project(client, admin_token)
    add_member(tmp_db, project_id=pid, user_id=viewer.id, role="viewer")
    viewer_token = client.post("/api/v1/auth/login", json={"username": "v2", "password": "p"}).json()["token"]

    resp = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T"}, headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 403


def test_create_and_delete_comment(client, admin_token) -> None:
    pid = _make_project(client, admin_token)
    task_id = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T"}, headers={"Authorization": f"Bearer {admin_token}"}).json()["id"]

    cid = client.post(f"/api/v1/projects/{pid}/tasks/{task_id}/comments", json={"body": "Note"}, headers={"Authorization": f"Bearer {admin_token}"}).json()["id"]
    del_resp = client.delete(f"/api/v1/projects/{pid}/tasks/{task_id}/comments/{cid}", headers={"Authorization": f"Bearer {admin_token}"})
    assert del_resp.status_code == 204

    comments = client.get(f"/api/v1/projects/{pid}/tasks/{task_id}/comments", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert comments == []


def test_legacy_critical_priority_is_folded_into_high(client, admin_token) -> None:
    """Task priority has three levels; "critical" from older clients is stored as "high"."""
    h = {"Authorization": f"Bearer {admin_token}"}
    pid = _make_project(client, admin_token)
    created = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T", "priority": "critical"}, headers=h)
    assert created.status_code == 201
    assert created.json()["priority"] == "high"

    updated = client.put(f"/api/v1/projects/{pid}/tasks/{created.json()['id']}", json={"priority": "critical"}, headers=h)
    assert updated.json()["priority"] == "high"


def test_schema_migration_folds_existing_critical_tasks(tmp_db, admin_token, client) -> None:
    from EvoScientist.pm.db import create_schema, get_db

    pid = _make_project(client, admin_token)
    tid = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T"}, headers={"Authorization": f"Bearer {admin_token}"}).json()["id"]
    with get_db(tmp_db) as conn:
        conn.execute("UPDATE tasks SET priority = 'critical' WHERE id = ?", (tid,))
    create_schema(tmp_db)
    with get_db(tmp_db) as conn:
        assert conn.execute("SELECT priority FROM tasks WHERE id = ?", (tid,)).fetchone()[0] == "high"
