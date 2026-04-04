"""Tests for /auth routes."""
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.users import create_user


def test_login_success(client, tmp_db) -> None:
    create_user(tmp_db, username="alice", password_hash=hash_password("pass123"))
    resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "pass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["username"] == "alice"


def test_login_wrong_password(client, tmp_db) -> None:
    create_user(tmp_db, username="bob", password_hash=hash_password("correct"))
    resp = client.post("/api/v1/auth/login", json={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(client) -> None:
    resp = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "x"})
    assert resp.status_code == 401


def test_protected_route_without_token(client) -> None:
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 422  # missing header


def test_protected_route_invalid_token(client) -> None:
    resp = client.get("/api/v1/users/me", headers={"Authorization": "Bearer badtoken"})
    assert resp.status_code == 401
