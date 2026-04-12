"""Tests for /projects routes and permission enforcement."""


def test_create_project(client, admin_token) -> None:
    resp = client.post(
        "/api/v1/projects",
        json={"name": "My Project"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Project"
    assert any(m["role"] == "owner" for m in data["members"])


def test_list_projects_only_own(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user
    create_user(tmp_db, username="other", password_hash=hash_password("p"))

    # Admin creates a project; other user should NOT see it
    client.post("/api/v1/projects", json={"name": "Secret"}, headers={"Authorization": f"Bearer {admin_token}"})

    other_token = client.post("/api/v1/auth/login", json={"username": "other", "password": "p"}).json()["token"]
    resp = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {other_token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_viewer_cannot_delete_project(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.projects import add_member
    from EvoScientist.pm.crud.users import create_user

    viewer = create_user(tmp_db, username="viewer", password_hash=hash_password("vp"))
    create_resp = client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {admin_token}"})
    project_id = create_resp.json()["id"]

    add_member(tmp_db, project_id=project_id, user_id=viewer.id, role="viewer")
    viewer_token = client.post("/api/v1/auth/login", json={"username": "viewer", "password": "vp"}).json()["token"]

    resp = client.delete(f"/api/v1/projects/{project_id}", headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 403


def test_nonmember_gets_403(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user

    create_user(tmp_db, username="outsider", password_hash=hash_password("op"))
    create_resp = client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {admin_token}"})
    project_id = create_resp.json()["id"]

    outsider_token = client.post("/api/v1/auth/login", json={"username": "outsider", "password": "op"}).json()["token"]
    resp = client.get(f"/api/v1/projects/{project_id}", headers={"Authorization": f"Bearer {outsider_token}"})
    assert resp.status_code == 403
