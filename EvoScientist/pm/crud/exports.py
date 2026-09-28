"""CRUD for export requests."""

from __future__ import annotations

from pathlib import Path

from ..db import get_db
from ..models import ExportRequest

_COLUMNS = "id, project_id, sandbox_id, requested_by, reviewed_by, status, file_name, file_type, file_size_bytes, description, justification, reviewer_notes, reviewed_at, created_at"


def _row_to_export(r: dict) -> ExportRequest:
    return ExportRequest(
        id=r["id"],
        project_id=r["project_id"],
        sandbox_id=r.get("sandbox_id"),
        requested_by=r["requested_by"],
        reviewed_by=r.get("reviewed_by"),
        status=r["status"],
        file_name=r["file_name"],
        file_type=r["file_type"],
        file_size_bytes=r.get("file_size_bytes"),
        description=r.get("description"),
        justification=r.get("justification"),
        reviewer_notes=r.get("reviewer_notes"),
        reviewed_at=r.get("reviewed_at"),
        created_at=r["created_at"],
    )


def create_export_request(
    db_path: str | Path,
    project_id: str,
    requested_by: str,
    file_name: str,
    file_type: str,
    sandbox_id: str | None = None,
    file_size_bytes: int | None = None,
    description: str | None = None,
    justification: str | None = None,
) -> ExportRequest:
    import uuid

    eid = str(uuid.uuid4())
    now = __import__("datetime").datetime.utcnow().isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            f"INSERT INTO export_requests ({_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                eid,
                project_id,
                sandbox_id,
                requested_by,
                None,
                "pending",
                file_name,
                file_type,
                file_size_bytes,
                description,
                justification,
                None,
                None,
                now,
            ),
        )
        return get_export_request(db_path, eid)


def get_export_request(db_path: str | Path, export_id: str) -> ExportRequest | None:
    with get_db(db_path) as conn:
        r = conn.execute(
            "SELECT * FROM export_requests WHERE id = ?", (export_id,)
        ).fetchone()
        return _row_to_export(r) if r else None


def list_export_requests(
    db_path: str | Path, project_id: str | None = None, status: str | None = None
) -> list[ExportRequest]:
    where = []
    vals = []
    if project_id:
        where.append("project_id = ?")
        vals.append(project_id)
    if status:
        where.append("status = ?")
        vals.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with get_db(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM export_requests {clause} ORDER BY created_at DESC", vals
        ).fetchall()
        return [_row_to_export(r) for r in rows]


def review_export_request(
    db_path: str | Path,
    export_id: str,
    reviewer_id: str,
    status: str,
    reviewer_notes: str | None = None,
) -> ExportRequest | None:
    now = __import__("datetime").datetime.utcnow().isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE export_requests SET status = ?, reviewed_by = ?, reviewer_notes = ?, reviewed_at = ? WHERE id = ?",
            (status, reviewer_id, reviewer_notes, now, export_id),
        )
        return get_export_request(db_path, export_id)


def delete_export_request(db_path: str | Path, export_id: str) -> bool:
    with get_db(db_path) as conn:
        c = conn.execute("DELETE FROM export_requests WHERE id = ?", (export_id,))
        return c.rowcount > 0
