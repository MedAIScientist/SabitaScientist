"""Shared fixtures for PM tests."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from gazzali.api.app import create_app
from gazzali.auth import hash_password
from gazzali.db import configure_db_path, create_schema


@pytest.fixture
def tmp_db(tmp_path: Path) -> Iterator[Path]:
    """A fresh PM database, bound process-wide for the duration of one test.

    Binding it here — instead of pointing each module's ``get_db_path`` at the
    file — is what ``create_app`` does in production too, so tests exercise the
    real resolution path. The binding is cleared afterwards, so no test can
    observe another test's database.
    """
    db_path = tmp_path / "projects.db"
    configure_db_path(db_path)
    create_schema(db_path)
    yield db_path
    configure_db_path(None)


@pytest.fixture
def db_conn(tmp_db: Path):
    """Yield an open sqlite3 connection to a fresh DB."""
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


@pytest.fixture
def app(tmp_db: Path):
    """Return a FastAPI test app bound to the temp DB."""
    return create_app(tmp_db)


@pytest.fixture
def client(app):
    """Synchronous TestClient for the FastAPI app."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def admin_user(tmp_db: Path):
    """Create and return an admin user in the temp DB."""
    from gazzali.crud.users import create_user
    return create_user(tmp_db, username="admin", password_hash=hash_password("adminpass"), is_admin=True)


@pytest.fixture
def admin_token(tmp_db: Path, admin_user, client):
    """Log in as admin and return the auth token."""
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "adminpass"})
    return resp.json()["token"]
