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
    assert resp.status_code == 401  # missing header


def test_protected_route_invalid_token(client) -> None:
    resp = client.get("/api/v1/users/me", headers={"Authorization": "Bearer badtoken"})
    assert resp.status_code == 401


def test_login_with_email(client, tmp_db) -> None:
    """SSO-created accounts carry an email — it must work as the identifier."""
    create_user(
        tmp_db,
        username="Alice Smith",
        password_hash=hash_password("pass123"),
        email="alice.smith@example.com",
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "alice.smith@example.com", "password": "pass123"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "Alice Smith"


def test_login_identifier_is_case_insensitive(client, tmp_db) -> None:
    create_user(
        tmp_db,
        username="Bob Jones",
        password_hash=hash_password("pass123"),
        email="Bob.Jones@Example.com",
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "bob jones", "password": "pass123"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"username": "bob.jones@example.com", "password": "pass123"},
        ).status_code
        == 200
    )


def test_login_with_email_wrong_password_is_rejected(client, tmp_db) -> None:
    create_user(
        tmp_db,
        username="carol",
        password_hash=hash_password("correct"),
        email="carol@example.com",
    )
    resp = client.post(
        "/api/v1/auth/login", json={"username": "carol@example.com", "password": "wrong"}
    )
    assert resp.status_code == 401


def test_login_accepts_identifier_with_surrounding_spaces(client, tmp_db) -> None:
    create_user(tmp_db, username="dave", password_hash=hash_password("pass123"))
    resp = client.post(
        "/api/v1/auth/login", json={"username": "  dave  ", "password": "pass123"}
    )
    assert resp.status_code == 200


def test_password_set_after_sso_login_unlocks_password_login(client, tmp_db) -> None:
    """A Microsoft-SSO account has an unusable random password; setting one works."""
    create_user(tmp_db, username="sso.user", password_hash=hash_password("random-secret"))
    first = client.post(
        "/api/v1/auth/login", json={"username": "sso.user", "password": "random-secret"}
    )
    token = first.json()["token"]

    resp = client.put(
        "/api/v1/users/me",
        json={"new_password": "chosen-password"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    again = client.post(
        "/api/v1/auth/login", json={"username": "sso.user", "password": "chosen-password"}
    )
    assert again.status_code == 200
