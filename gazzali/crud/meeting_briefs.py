"""Stored AI meeting briefs (per student) and group agendas (student_id NULL)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db


def save_brief(db_path: Path, *, professor_id: str, student_id: str | None, content: str) -> str:
    brief_id = uuid.uuid4().hex
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO meeting_briefs (id, professor_id, student_id, content, created_at) VALUES (?,?,?,?,?)",
            (brief_id, professor_id, student_id, content, datetime.now(UTC).isoformat()),
        )
    return brief_id


def latest_brief(db_path: Path, *, professor_id: str, student_id: str | None) -> dict | None:
    sql = ("SELECT id, student_id, content, created_at FROM meeting_briefs WHERE professor_id = ? AND "
           + ("student_id = ?" if student_id else "student_id IS NULL")
           + " ORDER BY created_at DESC LIMIT 1")
    params = (professor_id, student_id) if student_id else (professor_id,)
    with get_db(db_path) as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None
