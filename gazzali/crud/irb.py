"""CRUD operations for IRB approval entities."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import IRBApproval


def _row_to_irb(r) -> IRBApproval:
    return IRBApproval(
        id=r["id"],
        project_id=r["project_id"],
        institution=r["institution"],
        protocol_number=r["protocol_number"],
        title=r["title"],
        status=r["status"],
        approval_date=r["approval_date"],
        expiry_date=r["expiry_date"],
        renewal_date=r["renewal_date"],
        documents=json.loads(r["documents"]) if isinstance(r["documents"], str) else [],
        notes=r["notes"],
        created_by=r["created_by"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        approved_by=r["approved_by"] if "approved_by" in r.keys() else None,
        approved_at=r["approved_at"] if "approved_at" in r.keys() else None,
    )


def create_irb(
    db_path: Path,
    project_id: str,
    institution: str,
    protocol_number: str,
    title: str,
    created_by: str,
    status: str = "draft",
    approval_date: str | None = None,
    expiry_date: str | None = None,
    renewal_date: str | None = None,
    documents: list[str] | None = None,
    notes: str | None = None,
) -> IRBApproval:
    iid = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO irb_approvals (id,project_id,institution,protocol_number,title,status,approval_date,expiry_date,renewal_date,documents,notes,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                iid,
                project_id,
                institution,
                protocol_number,
                title,
                status,
                approval_date,
                expiry_date,
                renewal_date,
                json.dumps(documents or []),
                notes,
                created_by,
                now,
                now,
            ),
        )
    return IRBApproval(
        id=iid,
        project_id=project_id,
        institution=institution,
        protocol_number=protocol_number,
        title=title,
        status=status,
        approval_date=approval_date,
        expiry_date=expiry_date,
        renewal_date=renewal_date,
        documents=documents or [],
        notes=notes,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def list_irbs(
    db_path: Path,
    project_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[IRBApproval]:
    q = "SELECT * FROM irb_approvals WHERE 1=1"
    params: list = []
    if project_id:
        q += " AND project_id=?"
        params.append(project_id)
    if status:
        q += " AND status=?"
        params.append(status)
    q += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_db(db_path) as conn:
        return [_row_to_irb(r) for r in conn.execute(q, params).fetchall()]


def get_irb(db_path: Path, iid: str) -> IRBApproval | None:
    with get_db(db_path) as conn:
        r = conn.execute("SELECT * FROM irb_approvals WHERE id=?", (iid,)).fetchone()
    return _row_to_irb(r) if r else None


def update_irb(
    db_path: Path,
    iid: str,
    status: str | None = None,
    approval_date: str | None = None,
    expiry_date: str | None = None,
    renewal_date: str | None = None,
    documents: list[str] | None = None,
    notes: str | None = None,
    institution: str | None = None,
    protocol_number: str | None = None,
    approved_by: str | None = None,
    approved_at: str | None = None,
) -> IRBApproval | None:
    updates = {}
    if approved_by is not None:
        updates["approved_by"] = approved_by
    if approved_at is not None:
        updates["approved_at"] = approved_at
    if status is not None:
        updates["status"] = status
    if approval_date is not None:
        updates["approval_date"] = approval_date
    if expiry_date is not None:
        updates["expiry_date"] = expiry_date
    if renewal_date is not None:
        updates["renewal_date"] = renewal_date
    if documents is not None:
        updates["documents"] = json.dumps(documents)
    if notes is not None:
        updates["notes"] = notes
    if institution is not None:
        updates["institution"] = institution
    if protocol_number is not None:
        updates["protocol_number"] = protocol_number
    if updates:
        now = datetime.now(UTC).isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        with get_db(db_path) as conn:
            conn.execute(
                f"UPDATE irb_approvals SET {set_clause}, updated_at=? WHERE id=?",
                [*updates.values(), now, iid],
            )
    return get_irb(db_path, iid)


def delete_irb(db_path: Path, iid: str) -> bool:
    with get_db(db_path) as conn:
        return conn.execute("DELETE FROM irb_approvals WHERE id=?", (iid,)).rowcount > 0
