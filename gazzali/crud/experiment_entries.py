"""CRUD operations for ExperimentEntry entities."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import ExperimentEntry


def create_entry(
    db_path: Path,
    experiment_id: str,
    entry_type: str,
    title: str,
    body: str = "",
    author_id: str | None = None,
) -> ExperimentEntry:
    """Create an experiment entry (note or result) and return it."""
    entry_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO experiment_entries
               (id, experiment_id, type, title, body, author_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry_id, experiment_id, entry_type, title, body, author_id, now, now),
        )
    return ExperimentEntry(
        id=entry_id,
        experiment_id=experiment_id,
        type=entry_type,
        title=title,
        body=body,
        author_id=author_id,
        created_at=now,
        updated_at=now,
    )


def get_entry(db_path: Path, entry_id: str) -> ExperimentEntry | None:
    """Return ExperimentEntry by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM experiment_entries WHERE id = ?", (entry_id,)
        ).fetchone()
    return _row_to_entry(row) if row else None


def list_entries(
    db_path: Path,
    experiment_id: str,
    entry_type: str | None = None,
) -> list[ExperimentEntry]:
    """Return entries for an experiment, newest first. Optionally filter by type."""
    query = "SELECT * FROM experiment_entries WHERE experiment_id = ?"
    params: list = [experiment_id]
    if entry_type is not None:
        query += " AND type = ?"
        params.append(entry_type)
    query += " ORDER BY created_at DESC"
    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_entry(r) for r in rows]


def update_entry(
    db_path: Path,
    entry_id: str,
    title: str | None = None,
    body: str | None = None,
) -> ExperimentEntry:
    """Update entry title and/or body. Omitted kwargs are unchanged."""
    entry = get_entry(db_path, entry_id)
    if entry is None:
        raise ValueError(f"ExperimentEntry {entry_id!r} not found")
    now = datetime.now(UTC).isoformat()
    new = ExperimentEntry(
        id=entry.id,
        experiment_id=entry.experiment_id,
        type=entry.type,
        title=title if title is not None else entry.title,
        body=body if body is not None else entry.body,
        author_id=entry.author_id,
        created_at=entry.created_at,
        updated_at=now,
    )
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE experiment_entries SET title=?, body=?, updated_at=? WHERE id=?",
            (new.title, new.body, now, entry_id),
        )
    return new


def delete_entry(db_path: Path, entry_id: str) -> bool:
    """Delete an entry. Returns True if it existed."""
    with get_db(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM experiment_entries WHERE id = ?", (entry_id,)
        )
    return cur.rowcount > 0


def _row_to_entry(row: sqlite3.Row) -> ExperimentEntry:
    return ExperimentEntry(
        id=row["id"],
        experiment_id=row["experiment_id"],
        type=row["type"],
        title=row["title"],
        body=row["body"],
        author_id=row["author_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
