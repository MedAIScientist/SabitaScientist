"""CRUD operations for file attachments."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

from gazzali.models import Attachment

_COLUMNS = ("id, entry_id, task_id, filename, s3_key, content_type, size_bytes, "
            "uploaded_by, created_at, classification")


def _row_to_attachment(row: sqlite3.Row) -> Attachment:
    try:
        classification = row["classification"]
    except (KeyError, IndexError):
        classification = "unclassified"
    return Attachment(
        id=row["id"],
        entry_id=row["entry_id"],
        task_id=row["task_id"],
        filename=row["filename"],
        s3_key=row["s3_key"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        uploaded_by=row["uploaded_by"],
        created_at=row["created_at"],
        classification=classification,
    )


def create_attachment(
    db: sqlite3.Connection,
    entry_id: str | None,
    filename: str,
    s3_key: str,
    content_type: str,
    size_bytes: int,
    user_id: str | None = None,
    classification: str = "unclassified",
    *,
    task_id: str | None = None,
) -> Attachment:
    """Insert a new attachment record and return it.

    Exactly one owner: an experiment entry or a task. The table enforces this too,
    but failing here says which mistake was made.
    """
    if (entry_id is None) == (task_id is None):
        raise ValueError("an attachment belongs to exactly one owner: an entry or a task")
    attachment_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    db.execute(
        f"INSERT INTO attachments ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            attachment_id,
            entry_id,
            task_id,
            filename,
            s3_key,
            content_type,
            size_bytes,
            user_id,
            now,
            classification,
        ),
    )
    return Attachment(
        id=attachment_id,
        entry_id=entry_id,
        task_id=task_id,
        filename=filename,
        s3_key=s3_key,
        content_type=content_type,
        size_bytes=size_bytes,
        uploaded_by=user_id,
        created_at=now,
        classification=classification,
    )


def list_attachments(db: sqlite3.Connection, entry_id: str) -> list[Attachment]:
    """Return all attachments for an experiment entry, ordered by creation time."""
    rows = db.execute(
        "SELECT * FROM attachments WHERE entry_id = ? ORDER BY created_at ASC",
        (entry_id,),
    ).fetchall()
    return [_row_to_attachment(r) for r in rows]


def list_task_attachments(db: sqlite3.Connection, task_id: str) -> list[Attachment]:
    """Return all attachments for a task, oldest first."""
    rows = db.execute(
        "SELECT * FROM attachments WHERE task_id = ? ORDER BY created_at ASC",
        (task_id,),
    ).fetchall()
    return [_row_to_attachment(r) for r in rows]


def owner_project_id(db: sqlite3.Connection, attachment_id: str) -> str | None:
    """The project an attachment belongs to, whichever kind of owner it has.

    Ownership is polymorphic, so authorisation has to resolve the project through
    the owning row rather than trusting a caller-supplied id.
    """
    row = db.execute(
        """SELECT COALESCE(t.project_id, x.project_id) AS project_id
             FROM attachments a
             LEFT JOIN tasks t ON t.id = a.task_id
             LEFT JOIN experiment_entries e ON e.id = a.entry_id
             LEFT JOIN experiments x ON x.id = e.experiment_id
            WHERE a.id = ?""",
        (attachment_id,),
    ).fetchone()
    return row["project_id"] if row else None


def list_project_attachments(
    db: sqlite3.Connection, project_id: str, kind: str | None = None
) -> list[dict]:
    """Every file in a project, newest first, with what it is attached to.

    A file is attached to a task or to an experiment entry; a project-wide view has
    to answer both, so the two are unioned with the owner's name attached. The
    caller groups or filters; one query keeps the page a single request.
    """
    rows = db.execute(
        """SELECT * FROM (
               SELECT a.id, a.filename, a.content_type, a.size_bytes, a.classification,
                      a.created_at, a.uploaded_by, u.username AS uploader_name,
                      'task' AS owner_kind, t.id AS owner_id, t.title AS owner_title,
                      t.project_id AS project_id, NULL AS experiment_id
                 FROM attachments a
                 JOIN tasks t ON t.id = a.task_id
                 LEFT JOIN users u ON u.id = a.uploaded_by
                WHERE t.project_id = ?
               UNION ALL
               SELECT a.id, a.filename, a.content_type, a.size_bytes, a.classification,
                      a.created_at, a.uploaded_by, u.username AS uploader_name,
                      'entry' AS owner_kind, e.id AS owner_id, e.title AS owner_title,
                      x.project_id AS project_id, x.id AS experiment_id
                 FROM attachments a
                 JOIN experiment_entries e ON e.id = a.entry_id
                 JOIN experiments x ON x.id = e.experiment_id
                 LEFT JOIN users u ON u.id = a.uploaded_by
                WHERE x.project_id = ?
           )
           WHERE (? IS NULL OR owner_kind = ?)
           ORDER BY created_at DESC""",
        (project_id, project_id, kind, kind),
    ).fetchall()
    return [dict(r) for r in rows]


def get_attachment(db: sqlite3.Connection, attachment_id: str) -> Attachment | None:
    """Return an attachment by its primary key, or None if not found."""
    row = db.execute(
        "SELECT * FROM attachments WHERE id = ?", (attachment_id,)
    ).fetchone()
    return _row_to_attachment(row) if row else None


def update_attachment_classification(
    db: sqlite3.Connection, attachment_id: str, classification: str
) -> Attachment | None:
    """Update the data classification of an attachment."""
    db.execute(
        "UPDATE attachments SET classification = ? WHERE id = ?",
        (classification, attachment_id),
    )
    return get_attachment(db, attachment_id)


def delete_attachment(db: sqlite3.Connection, attachment_id: str) -> None:
    """Delete an attachment record (caller is responsible for removing the S3 object)."""
    db.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
