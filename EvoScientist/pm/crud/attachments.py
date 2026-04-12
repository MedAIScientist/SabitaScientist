"""CRUD operations for file attachments."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from EvoScientist.pm.models import Attachment


def _row_to_attachment(row: sqlite3.Row) -> Attachment:
    return Attachment(
        id=row["id"],
        entry_id=row["entry_id"],
        filename=row["filename"],
        s3_key=row["s3_key"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        uploaded_by=row["uploaded_by"],
        created_at=row["created_at"],
    )


def create_attachment(
    db: sqlite3.Connection,
    entry_id: str,
    filename: str,
    s3_key: str,
    content_type: str,
    size_bytes: int,
    user_id: str | None = None,
) -> Attachment:
    """Insert a new attachment record and return it."""
    attachment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """
        INSERT INTO attachments (id, entry_id, filename, s3_key, content_type,
                                  size_bytes, uploaded_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (attachment_id, entry_id, filename, s3_key, content_type,
         size_bytes, user_id, now),
    )
    return Attachment(
        id=attachment_id,
        entry_id=entry_id,
        filename=filename,
        s3_key=s3_key,
        content_type=content_type,
        size_bytes=size_bytes,
        uploaded_by=user_id,
        created_at=now,
    )


def list_attachments(db: sqlite3.Connection, entry_id: str) -> list[Attachment]:
    """Return all attachments for an experiment entry, ordered by creation time."""
    rows = db.execute(
        "SELECT * FROM attachments WHERE entry_id = ? ORDER BY created_at ASC",
        (entry_id,),
    ).fetchall()
    return [_row_to_attachment(r) for r in rows]


def get_attachment(
    db: sqlite3.Connection, attachment_id: str
) -> Attachment | None:
    """Return an attachment by its primary key, or None if not found."""
    row = db.execute(
        "SELECT * FROM attachments WHERE id = ?", (attachment_id,)
    ).fetchone()
    return _row_to_attachment(row) if row else None


def delete_attachment(db: sqlite3.Connection, attachment_id: str) -> None:
    """Delete an attachment record (caller is responsible for removing the S3 object)."""
    db.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
