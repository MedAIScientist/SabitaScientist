"""Regression tests for the OIDC callback (SSO) user provisioning."""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.api.routes import auth_oidc as auth_oidc_mod
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.users import (
    create_user,
    get_user_by_email,
    get_user_by_username,
)
from EvoScientist.pm.oidc import OIDCUser


def _patch_oidc(monkeypatch, db_path, oidc_user):
    """Point the OIDC route at a temp DB and a fake provider response."""
    monkeypatch.setattr(auth_oidc_mod, "get_db_path", lambda: db_path)

    async def fake_exchange(code: str):
        return oidc_user

    monkeypatch.setattr(auth_oidc_mod, "exchange_code", fake_exchange)


def _callback(client: TestClient, state: str) -> TestClient.response:
    auth_oidc_mod._oidc_states[state] = "/login"
    return client.get(
        f"/api/v1/auth/oidc/callback?code=code123&state={state}",
        follow_redirects=False,
    )


def _make_client(tmp_db):
    return TestClient(create_app(tmp_db))


def test_oidc_callback_reuses_existing_user_with_same_email(tmp_db, monkeypatch):
    """Regression: a user matching by email but not by display name must not
    trigger a UNIQUE(email) violation on create."""
    create_user(
        tmp_db,
        username="Alice Local",
        password_hash=hash_password("pw"),
        email="alice@medipol.edu.tr",
    )
    oidc_user = OIDCUser(
        sub="sub-123",
        email="alice@medipol.edu.tr",
        name="Alice Yeni Isim",
        preferred_username=None,
        issuer="https://login.microsoftonline.com/tenant/v2.0",
    )
    _patch_oidc(monkeypatch, tmp_db, oidc_user)

    resp = _callback(_make_client(tmp_db), "state1")

    assert resp.status_code == 307
    assert "token=" in resp.headers["location"]
    user = get_user_by_email(tmp_db, "alice@medipol.edu.tr")
    assert user is not None
    assert user.username == "Alice Local"
    assert get_user_by_username(tmp_db, "Alice Yeni Isim") is None


def test_oidc_callback_creates_new_user(tmp_db, monkeypatch):
    oidc_user = OIDCUser(
        sub="sub-456",
        email="bob@medipol.edu.tr",
        name="Bob",
        preferred_username=None,
        issuer="https://login.microsoftonline.com/tenant/v2.0",
    )
    _patch_oidc(monkeypatch, tmp_db, oidc_user)

    resp = _callback(_make_client(tmp_db), "state2")

    assert resp.status_code == 307
    user = get_user_by_email(tmp_db, "bob@medipol.edu.tr")
    assert user is not None
    assert user.username == "Bob"


def test_oidc_callback_repeated_login_does_not_duplicate(tmp_db, monkeypatch):
    oidc_user = OIDCUser(
        sub="sub-789",
        email="carol@medipol.edu.tr",
        name="Carol",
        preferred_username=None,
        issuer="https://login.microsoftonline.com/tenant/v2.0",
    )
    _patch_oidc(monkeypatch, tmp_db, oidc_user)
    client = _make_client(tmp_db)

    resp1 = _callback(client, "state3")
    resp2 = _callback(client, "state4")

    assert resp1.status_code == 307
    assert resp2.status_code == 307
    user = get_user_by_email(tmp_db, "carol@medipol.edu.tr")
    assert user is not None
    with sqlite3.connect(tmp_db) as conn:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM users WHERE email = ?", ("carol@medipol.edu.tr",)
        ).fetchone()
    assert count == 1
