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
    from gazzali.auth import hash_password
    from gazzali.crud.projects import add_member
    from gazzali.crud.users import create_user

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
    from gazzali.db import create_schema, get_db

    pid = _make_project(client, admin_token)
    tid = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T"}, headers={"Authorization": f"Bearer {admin_token}"}).json()["id"]
    with get_db(tmp_db) as conn:
        conn.execute("UPDATE tasks SET priority = 'critical' WHERE id = ?", (tid,))
    create_schema(tmp_db)
    with get_db(tmp_db) as conn:
        assert conn.execute("SELECT priority FROM tasks WHERE id = ?", (tid,)).fetchone()[0] == "high"


def _make_phase(client, token, pid: str, name: str) -> str:
    resp = client.post(
        f"/api/v1/projects/{pid}/phases",
        json={"name": name, "position": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_a_task_can_be_created_in_a_phase(client, admin_token) -> None:
    """Adding a task from a phase's column must place it there, not under 'Unassigned'."""
    pid = _make_project(client, admin_token)
    phase = _make_phase(client, admin_token, pid, "Data Analysis")

    created = client.post(
        f"/api/v1/projects/{pid}/tasks",
        json={"title": "Denoise cohort", "phase_id": phase},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert created.status_code == 201, created.text
    assert created.json()["phase_id"] == phase
    # …and it survives a re-read, not just the create response.
    listed = client.get(f"/api/v1/projects/{pid}/tasks", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert [t["phase_id"] for t in listed] == [phase]


def test_a_task_created_without_a_phase_stays_unassigned(client, admin_token) -> None:
    pid = _make_project(client, admin_token)
    created = client.post(
        f"/api/v1/projects/{pid}/tasks",
        json={"title": "Loose end"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["phase_id"] is None


def test_a_phase_from_another_project_is_refused(client, admin_token) -> None:
    """Otherwise the task would be parked where nobody looking at this board can see it."""
    pid = _make_project(client, admin_token)
    other = _make_project(client, admin_token)
    foreign_phase = _make_phase(client, admin_token, other, "Someone else's lane")

    resp = client.post(
        f"/api/v1/projects/{pid}/tasks",
        json={"title": "Misfiled", "phase_id": foreign_phase},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400

    listed = client.get(f"/api/v1/projects/{pid}/tasks", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert listed == [], "the task was created despite the bad phase"


def test_an_unknown_phase_is_refused(client, admin_token) -> None:
    pid = _make_project(client, admin_token)
    resp = client.post(
        f"/api/v1/projects/{pid}/tasks",
        json={"title": "Nowhere", "phase_id": "no-such-phase"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
