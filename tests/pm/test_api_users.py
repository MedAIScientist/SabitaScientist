"""Tests for /users/search endpoint."""


def test_search_returns_empty_for_short_query(client, admin_token) -> None:
    resp = client.get(
        "/api/v1/users/search?q=",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_returns_matching_users(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user

    create_user(tmp_db, username="alice_lab", password_hash=hash_password("p"))
    create_user(tmp_db, username="bob_lab", password_hash=hash_password("p"))

    resp = client.get(
        "/api/v1/users/search?q=alice",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["username"] == "alice_lab"
    assert "id" in data[0]
    # Must NOT expose email, password_hash, or is_admin
    assert "email" not in data[0]
    assert "password_hash" not in data[0]
    assert "is_admin" not in data[0]


def test_search_is_case_insensitive(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user

    create_user(tmp_db, username="ALICE_LAB", password_hash=hash_password("p"))

    resp = client.get(
        "/api/v1/users/search?q=alice",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_search_requires_authentication(client) -> None:
    resp = client.get("/api/v1/users/search?q=alice")
    assert resp.status_code == 401
