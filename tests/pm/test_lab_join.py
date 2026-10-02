"""A student asks to join a lab; only that lab's PI/admin decides; approval makes them supervised."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.supervision_scope import supervises


def _login(client, name):
    tok = client.post("/api/v1/auth/login", json={"username": name, "password": "pw123456"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def test_join_request_flow(tmp_db: Path) -> None:
    prof = create_user(tmp_db, "kaya", hash_password("pw123456"), email="kaya@medipol.edu.tr")
    create_user(tmp_db, "other", hash_password("pw123456"), email="other@medipol.edu.tr")
    stud = create_user(tmp_db, "ayse", hash_password("pw123456"), email="ayse@std.medipol.edu.tr")
    client = TestClient(create_app(tmp_db))
    hp, ho, hs = _login(client, "kaya"), _login(client, "other"), _login(client, "ayse")

    lab = client.post("/api/v1/labs", json={"name": "Retina Lab"}, headers=hp).json()
    assert client.post(f"/api/v1/labs/{lab['id']}/join-requests", json={}, headers=hp).status_code == 403

    r = client.post(f"/api/v1/labs/{lab['id']}/join-requests", json={"lab_role": "ms", "message": "hi"}, headers=hs)
    assert r.status_code == 201
    req = r.json()
    assert client.post(f"/api/v1/labs/{lab['id']}/join-requests", json={}, headers=hs).status_code == 409
    assert not supervises(tmp_db, prof.id, stud.id)

    assert client.get("/api/v1/labs/join-requests/pending", headers=ho).json() == []
    assert client.post(f"/api/v1/labs/{lab['id']}/join-requests/{req['id']}/approve", headers=ho).status_code == 404
    assert client.post(f"/api/v1/labs/{lab['id']}/join-requests/{req['id']}/approve", headers=hs).status_code == 404

    assert [p["id"] for p in client.get("/api/v1/labs/join-requests/pending", headers=hp).json()] == [req["id"]]
    r = client.post(f"/api/v1/labs/{lab['id']}/join-requests/{req['id']}/approve", headers=hp)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert supervises(tmp_db, prof.id, stud.id)
    assert client.post(f"/api/v1/labs/{lab['id']}/join-requests/{req['id']}/decline", headers=hp).status_code == 409
    assert client.get("/api/v1/labs/join-requests/mine", headers=hs).json()[0]["status"] == "approved"
    assert client.post(f"/api/v1/labs/{lab['id']}/join-requests", json={}, headers=hs).status_code == 409  # already member
