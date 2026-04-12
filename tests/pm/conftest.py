"""Shared fixtures for PM tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from EvoScientist.pm.db import create_schema, get_db
from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.auth import hash_password


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return path to a fresh temporary projects.db."""
    db_path = tmp_path / "projects.db"
    create_schema(db_path)
    return db_path


@pytest.fixture
def db_conn(tmp_db: Path):
    """Yield an open sqlite3 connection to a fresh DB."""
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


def monkeypatch_db(db_path: Path, *modules) -> None:
    """Replace get_db_path() in each module to return db_path."""
    for mod in modules:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda: db_path


@pytest.fixture
def app(tmp_db: Path):
    """Return a FastAPI test app backed by a temp DB."""
    import EvoScientist.pm.api.deps as deps_mod
    import EvoScientist.pm.auth as auth_mod
    import EvoScientist.pm.crud.users as users_mod
    import EvoScientist.pm.crud.projects as projects_mod
    import EvoScientist.pm.crud.tasks as tasks_mod
    import EvoScientist.pm.api.routes.auth as auth_routes_mod
    import EvoScientist.pm.api.routes.users as users_routes_mod
    import EvoScientist.pm.api.routes.projects as projects_routes_mod
    import EvoScientist.pm.api.routes.tasks as tasks_routes_mod
    import EvoScientist.pm.api.routes.phases as phases_routes_mod

    # Patch all DB path lookups to use the temp DB
    monkeypatch_db(
        tmp_db, deps_mod, auth_mod, users_mod, projects_mod, tasks_mod,
        auth_routes_mod, users_routes_mod, projects_routes_mod, tasks_routes_mod,
        phases_routes_mod,
    )
    return create_app(tmp_db)


@pytest.fixture
def client(app):
    """Synchronous TestClient for the FastAPI app."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def admin_user(tmp_db: Path):
    """Create and return an admin user in the temp DB."""
    from EvoScientist.pm.crud.users import create_user
    return create_user(tmp_db, username="admin", password_hash=hash_password("adminpass"), is_admin=True)


@pytest.fixture
def admin_token(tmp_db: Path, admin_user, client):
    """Log in as admin and return the auth token."""
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "adminpass"})
    return resp.json()["token"]
