"""Tests for user CRUD operations."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from EvoScientist.pm.crud.users import (
    create_user,
    delete_user,
    get_user_by_id,
    get_user_by_username,
    list_users,
    update_user_password,
)
from EvoScientist.pm.db import create_schema


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    return db_path


def test_create_user_and_retrieve(db: Path) -> None:
    user = create_user(db, username="alice", password_hash="hash_a", is_admin=True)
    assert user.id is not None
    assert user.username == "alice"
    assert user.is_admin is True

    fetched = get_user_by_id(db, user.id)
    assert fetched is not None
    assert fetched.username == "alice"


def test_get_user_by_username(db: Path) -> None:
    create_user(db, username="bob", password_hash="hash_b")
    user = get_user_by_username(db, "bob")
    assert user is not None
    assert user.username == "bob"


def test_get_user_by_username_missing(db: Path) -> None:
    assert get_user_by_username(db, "ghost") is None


def test_duplicate_username_raises(db: Path) -> None:
    create_user(db, username="carol", password_hash="h")
    with pytest.raises(sqlite3.IntegrityError):
        create_user(db, username="carol", password_hash="h2")


def test_list_users(db: Path) -> None:
    create_user(db, username="u1", password_hash="h1")
    create_user(db, username="u2", password_hash="h2")
    users = list_users(db)
    assert len(users) == 2
    assert {u.username for u in users} == {"u1", "u2"}


def test_delete_user(db: Path) -> None:
    user = create_user(db, username="dave", password_hash="hd")
    assert delete_user(db, user.id) is True
    assert get_user_by_id(db, user.id) is None


def test_delete_nonexistent_user(db: Path) -> None:
    assert delete_user(db, "no-such-id") is False


def test_update_user_password(db: Path) -> None:
    user = create_user(db, username="eve", password_hash="old_hash")
    update_user_password(db, user.id, "new_hash")
    fetched = get_user_by_id(db, user.id)
    assert fetched.password_hash == "new_hash"
