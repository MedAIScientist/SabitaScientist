"""Shared fixtures for PM tests."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from EvoScientist.pm.db import create_schema, get_db


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
