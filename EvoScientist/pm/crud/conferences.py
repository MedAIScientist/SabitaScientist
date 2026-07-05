from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Conference


def create_conference(db_path: Path, **kw) -> Conference:
    cid, now = uuid.uuid4().hex, datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO conferences (id,project_id,publication_id,name,venue,location,deadline,submission_date,decision_date,status,presentation_type,travel_funding,travel_notes,url,notes,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                cid,
                kw.get("project_id"),
                kw.get("publication_id"),
                kw["name"],
                kw.get("venue"),
                kw.get("location"),
                kw.get("deadline"),
                kw.get("submission_date"),
                kw.get("decision_date"),
                kw.get("status", "draft"),
                kw.get("presentation_type", "poster"),
                kw.get("travel_funding"),
                kw.get("travel_notes"),
                kw.get("url"),
                kw.get("notes"),
                kw["created_by"],
                now,
                now,
            ),
        )
    return Conference(
        id=cid,
        name=kw["name"],
        status=kw.get("status", "draft"),
        presentation_type=kw.get("presentation_type", "poster"),
        created_by=kw["created_by"],
        created_at=now,
        updated_at=now,
        project_id=kw.get("project_id"),
        publication_id=kw.get("publication_id"),
        venue=kw.get("venue"),
        location=kw.get("location"),
        deadline=kw.get("deadline"),
        submission_date=kw.get("submission_date"),
        decision_date=kw.get("decision_date"),
        travel_funding=kw.get("travel_funding"),
        travel_notes=kw.get("travel_notes"),
        url=kw.get("url"),
        notes=kw.get("notes"),
    )


def list_conferences(
    db_path: Path,
    project_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Conference]:
    q = "SELECT * FROM conferences WHERE 1=1"
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
            Conference(
                id=r["id"],
                name=r["name"],
                status=r["status"],
                presentation_type=r["presentation_type"],
                created_by=r["created_by"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                project_id=r["project_id"],
                publication_id=r["publication_id"],
                venue=r["venue"],
                location=r["location"],
                deadline=r["deadline"],
                submission_date=r["submission_date"],
                decision_date=r["decision_date"],
                travel_funding=r["travel_funding"],
                travel_notes=r["travel_notes"],
                url=r["url"],
                notes=r["notes"],
            )
            for r in conn.execute(q, p).fetchall()
        ]


def get_conference(db_path: Path, cid: str) -> Conference | None:
    with get_db(db_path) as conn:
        r = conn.execute("SELECT * FROM conferences WHERE id=?", (cid,)).fetchone()
    return (
        Conference(
            id=r["id"],
            name=r["name"],
            status=r["status"],
            presentation_type=r["presentation_type"],
            created_by=r["created_by"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            project_id=r["project_id"],
            publication_id=r["publication_id"],
            venue=r["venue"],
            location=r["location"],
            deadline=r["deadline"],
            submission_date=r["submission_date"],
            decision_date=r["decision_date"],
            travel_funding=r["travel_funding"],
            travel_notes=r["travel_notes"],
            url=r["url"],
            notes=r["notes"],
        )
        if r
        else None
    )


def update_conference(db_path: Path, cid: str, **kw) -> Conference | None:
    allowed = {
        "name",
        "venue",
        "location",
        "deadline",
        "submission_date",
        "decision_date",
        "status",
        "presentation_type",
        "travel_funding",
        "travel_notes",
        "url",
        "notes",
        "project_id",
        "publication_id",
    }
    updates = {k: v for k, v in kw.items() if k in allowed and v is not None}
    if updates:
        now = datetime.now(UTC).isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        with get_db(db_path) as conn:
            conn.execute(
                f"UPDATE conferences SET {set_clause}, updated_at=? WHERE id=?",
                [*updates.values(), now, cid],
            )
    return get_conference(db_path, cid)


def delete_conference(db_path: Path, cid: str) -> bool:
    with get_db(db_path) as conn:
        return conn.execute("DELETE FROM conferences WHERE id=?", (cid,)).rowcount > 0
