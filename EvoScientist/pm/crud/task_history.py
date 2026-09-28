"""CRUD for task history (status change audit trail)."""

from __future__ import annotations

import sqlite3

from ..models import TaskHistoryEntry


def record_task_change(
    db: sqlite3.Connection,
    task_id: str,
    changed_by: str | None,
    change_type: str,
    from_status: str | None = None,
    to_status: str | None = None,
    comment: str | None = None,
) -> TaskHistoryEntry:
    import uuid
    hid = str(uuid.uuid4())
    now = __import__("datetime").datetime.utcnow().isoformat()
    db.execute(
        "INSERT INTO task_history (id, task_id, changed_by, from_status, to_status, change_type, comment, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (hid, task_id, changed_by, from_status, to_status, change_type, comment, now),
    )
    return TaskHistoryEntry(
        id=hid, task_id=task_id, changed_by=changed_by,
        from_status=from_status, to_status=to_status,
        change_type=change_type, comment=comment, created_at=now,
    )


def list_task_history(db: sqlite3.Connection, task_id: str) -> list[TaskHistoryEntry]:
    rows = db.execute(
        "SELECT * FROM task_history WHERE task_id = ? ORDER BY created_at DESC", (task_id,)
    ).fetchall()
    result = []
    for r in rows:
        result.append(TaskHistoryEntry(
            id=r["id"], task_id=r["task_id"], changed_by=r.get("changed_by"),
            from_status=r.get("from_status"), to_status=r.get("to_status"),
            change_type=r["change_type"], comment=r.get("comment"),
            created_at=r["created_at"],
        ))
    return result
