from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Grant


def create_grant(db_path: Path, **kw) -> Grant:
    gid, now = uuid.uuid4().hex, datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO grants (id,lab_id,project_id,title,funder,amount_requested,amount_awarded,currency,status,submitted_at,awarded_at,start_date,end_date,description,pi_id,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                gid,
                kw.get("lab_id"),
                kw.get("project_id"),
                kw["title"],
                kw["funder"],
                kw.get("amount_requested"),
                kw.get("amount_awarded"),
                kw.get("currency", "TRY"),
                kw.get("status", "draft"),
                kw.get("submitted_at"),
                kw.get("awarded_at"),
                kw.get("start_date"),
                kw.get("end_date"),
                kw.get("description"),
                kw.get("pi_id"),
                kw["created_by"],
                now,
                now,
            ),
        )
    return Grant(
        id=gid,
        title=kw["title"],
        funder=kw["funder"],
        status=kw.get("status", "draft"),
        created_by=kw["created_by"],
        created_at=now,
        updated_at=now,
        lab_id=kw.get("lab_id"),
        project_id=kw.get("project_id"),
        amount_requested=kw.get("amount_requested"),
        amount_awarded=kw.get("amount_awarded"),
        currency=kw.get("currency", "TRY"),
        submitted_at=kw.get("submitted_at"),
        awarded_at=kw.get("awarded_at"),
        start_date=kw.get("start_date"),
        end_date=kw.get("end_date"),
        description=kw.get("description"),
        pi_id=kw.get("pi_id"),
    )


def list_grants(
    db_path: Path,
    lab_id: str | None = None,
    project_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Grant]:
    q = "SELECT * FROM grants WHERE 1=1"
    p: list = []
    if lab_id:
        q += " AND lab_id=?"
        p.append(lab_id)
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
            Grant(
                id=r["id"],
                title=r["title"],
                funder=r["funder"],
                status=r["status"],
                created_by=r["created_by"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                lab_id=r["lab_id"],
                project_id=r["project_id"],
                amount_requested=r["amount_requested"],
                amount_awarded=r["amount_awarded"],
                currency=r.get("currency", "TRY"),
                submitted_at=r["submitted_at"],
                awarded_at=r["awarded_at"],
                start_date=r["start_date"],
                end_date=r["end_date"],
                description=r["description"],
                pi_id=r["pi_id"],
            )
            for r in conn.execute(q, p).fetchall()
        ]


def get_grant(db_path: Path, gid: str) -> Grant | None:
    with get_db(db_path) as conn:
        r = conn.execute("SELECT * FROM grants WHERE id=?", (gid,)).fetchone()
    return (
        Grant(
            id=r["id"],
            title=r["title"],
            funder=r["funder"],
            status=r["status"],
            created_by=r["created_by"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            lab_id=r["lab_id"],
            project_id=r["project_id"],
            amount_requested=r["amount_requested"],
            amount_awarded=r["amount_awarded"],
            currency=r.get("currency", "TRY"),
            submitted_at=r["submitted_at"],
            awarded_at=r["awarded_at"],
            start_date=r["start_date"],
            end_date=r["end_date"],
            description=r["description"],
            pi_id=r["pi_id"],
        )
        if r
        else None
    )


def update_grant(db_path: Path, gid: str, **kw) -> Grant | None:
    allowed = {
        "title",
        "funder",
        "amount_requested",
        "amount_awarded",
        "currency",
        "status",
        "submitted_at",
        "awarded_at",
        "start_date",
        "end_date",
        "description",
        "pi_id",
        "lab_id",
        "project_id",
    }
    updates = {k: v for k, v in kw.items() if k in allowed and v is not None}
    if updates:
        now = datetime.now(UTC).isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        with get_db(db_path) as conn:
            conn.execute(
                f"UPDATE grants SET {set_clause}, updated_at=? WHERE id=?",
                [*updates.values(), now, gid],
            )
    return get_grant(db_path, gid)


def delete_grant(db_path: Path, gid: str) -> bool:
    with get_db(db_path) as conn:
        return conn.execute("DELETE FROM grants WHERE id=?", (gid,)).rowcount > 0
