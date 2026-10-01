"""Supervision follow-ups: requests made in a weekly-report review that carry forward
week after week until the student or supervisor closes them."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import SupervisionFollowup

_COLS = "id, student_id, professor_id, report_id, text, due_date, status, student_note, created_at, closed_at"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row(r) -> SupervisionFollowup:
    return SupervisionFollowup(**{k: r[k] for k in r.keys()})


def create_followups(
    db_path: Path, *, student_id: str, professor_id: str, report_id: str | None,
    items: list[tuple[str, str | None]],
) -> list[SupervisionFollowup]:
    """Create one follow-up per (text, due_date); blank texts are skipped."""
    ids = []
    with get_db(db_path) as conn:
        for text, due in items:
            if not text.strip():
                continue
            fid = uuid.uuid4().hex
            conn.execute(
                f"INSERT INTO supervision_followups ({_COLS}) VALUES (?,?,?,?,?,?,'open',NULL,?,NULL)",
                (fid, student_id, professor_id, report_id, text.strip(), due or None, _now()),
            )
            ids.append(fid)
    return [f for f in (get_followup(db_path, i) for i in ids) if f]


def get_followup(db_path: Path, followup_id: str) -> SupervisionFollowup | None:
    with get_db(db_path) as conn:
        r = conn.execute(f"SELECT {_COLS} FROM supervision_followups WHERE id = ?", (followup_id,)).fetchone()
    return _row(r) if r else None


def list_followups(
    db_path: Path, *, student_ids: list[str] | None = None, status: str | None = None,
) -> list[SupervisionFollowup]:
    """Oldest open first: the longest-ignored request is the one to raise."""
    sql = f"SELECT {_COLS} FROM supervision_followups"
    where, params = [], []
    if student_ids is not None:
        if not student_ids:
            return []
        where.append(f"student_id IN ({','.join('?' * len(student_ids))})")
        params += student_ids
    if status:
        where.append("status = ?")
        params.append(status)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END, created_at"
    with get_db(db_path) as conn:
        return [_row(r) for r in conn.execute(sql, params).fetchall()]


def set_status(
    db_path: Path, followup_id: str, status: str, note: str | None = None,
) -> SupervisionFollowup | None:
    closed = _now() if status in ("done", "dropped") else None
    with get_db(db_path) as conn:
        if note is None:
            conn.execute("UPDATE supervision_followups SET status = ?, closed_at = ? WHERE id = ?",
                         (status, closed, followup_id))
        else:
            conn.execute("UPDATE supervision_followups SET status = ?, closed_at = ?, student_note = ? WHERE id = ?",
                         (status, closed, note, followup_id))
    return get_followup(db_path, followup_id)
