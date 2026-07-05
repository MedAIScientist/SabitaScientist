from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import IRBApproval


def create_irb(db_path: Path, **kw) -> IRBApproval:
    iid, now = uuid.uuid4().hex, datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO irb_approvals (id,project_id,institution,protocol_number,title,status,approval_date,expiry_date,renewal_date,documents,notes,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                iid,
                kw["project_id"],
                kw["institution"],
                kw["protocol_number"],
                kw["title"],
                kw.get("status", "draft"),
                kw.get("approval_date"),
                kw.get("expiry_date"),
                kw.get("renewal_date"),
                json.dumps(kw.get("documents", [])),
                kw.get("notes"),
                kw["created_by"],
                now,
                now,
            ),
        )
    return IRBApproval(
        id=iid,
        project_id=kw["project_id"],
        institution=kw["institution"],
        protocol_number=kw["protocol_number"],
        title=kw["title"],
        status=kw.get("status", "draft"),
        created_by=kw["created_by"],
        created_at=now,
        updated_at=now,
        approval_date=kw.get("approval_date"),
        expiry_date=kw.get("expiry_date"),
        renewal_date=kw.get("renewal_date"),
        documents=kw.get("documents"),
        notes=kw.get("notes"),
    )


def list_irbs(
    db_path: Path,
    project_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[IRBApproval]:
    q = "SELECT * FROM irb_approvals WHERE 1=1"
    p: list = []
    if project_id:
        q += " AND project_id=?"
        p.append(project_id)
    if status:
        q += " AND status=?"
        p.append(status)
    q += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    p.extend([limit, offset])
    with get_db(db_path) as conn:
        return [
            IRBApproval(
                id=r["id"],
                project_id=r["project_id"],
                institution=r["institution"],
                protocol_number=r["protocol_number"],
                title=r["title"],
                status=r["status"],
                created_by=r["created_by"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                approval_date=r["approval_date"],
                expiry_date=r["expiry_date"],
                renewal_date=r["renewal_date"],
                documents=json.loads(r["documents"])
                if isinstance(r["documents"], str)
                else [],
                notes=r["notes"],
            )
            for r in conn.execute(q, p).fetchall()
        ]


def get_irb(db_path: Path, iid: str) -> IRBApproval | None:
    with get_db(db_path) as conn:
        r = conn.execute("SELECT * FROM irb_approvals WHERE id=?", (iid,)).fetchone()
    return (
        IRBApproval(
            id=r["id"],
            project_id=r["project_id"],
            institution=r["institution"],
            protocol_number=r["protocol_number"],
            title=r["title"],
            status=r["status"],
            created_by=r["created_by"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            approval_date=r["approval_date"],
            expiry_date=r["expiry_date"],
            renewal_date=r["renewal_date"],
            documents=json.loads(r["documents"])
            if isinstance(r["documents"], str)
            else [],
            notes=r["notes"],
        )
        if r
        else None
    )


def update_irb(db_path: Path, iid: str, **kw) -> IRBApproval | None:
    allowed = {
        "status",
        "approval_date",
        "expiry_date",
        "renewal_date",
        "documents",
        "notes",
        "institution",
        "protocol_number",
    }
    updates = {k: v for k, v in kw.items() if k in allowed and v is not None}
    if "documents" in updates and isinstance(updates["documents"], list):
        updates["documents"] = json.dumps(updates["documents"])
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
