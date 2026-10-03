"""CRUD operations for Conference entities."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Conference


def _row_to_conference(r) -> Conference:
    return Conference(
        id=r["id"],
        name=r["name"],
        venue=r["venue"],
        location=r["location"],
        deadline=r["deadline"],
        submission_date=r["submission_date"],
        decision_date=r["decision_date"],
        status=r["status"],
        presentation_type=r["presentation_type"],
        travel_funding=r["travel_funding"],
        travel_notes=r["travel_notes"],
        url=r["url"],
        notes=r["notes"],
        project_id=r["project_id"],
        publication_id=r["publication_id"],
        created_by=r["created_by"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def create_conference(
    db_path: Path,
    name: str,
    created_by: str,
    project_id: str | None = None,
    publication_id: str | None = None,
    venue: str | None = None,
    location: str | None = None,
    deadline: str | None = None,
    submission_date: str | None = None,
    decision_date: str | None = None,
    status: str = "draft",
    presentation_type: str = "poster",
    travel_funding: float | None = None,
    travel_notes: str | None = None,
    url: str | None = None,
    notes: str | None = None,
) -> Conference:
    cid = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO conferences (id,project_id,publication_id,name,venue,location,deadline,submission_date,decision_date,status,presentation_type,travel_funding,travel_notes,url,notes,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                cid,
                project_id,
                publication_id,
                name,
                venue,
                location,
                deadline,
                submission_date,
                decision_date,
                status,
                presentation_type,
                travel_funding,
                travel_notes,
                url,
                notes,
                created_by,
                now,
                now,
            ),
        )
    return Conference(
        id=cid,
        name=name,
        venue=venue,
        location=location,
        deadline=deadline,
        submission_date=submission_date,
        decision_date=decision_date,
        status=status,
        presentation_type=presentation_type,
        travel_funding=travel_funding,
        travel_notes=travel_notes,
        url=url,
        notes=notes,
        project_id=project_id,
        publication_id=publication_id,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def list_conferences(
    db_path: Path,
    project_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Conference]:
    q = "SELECT * FROM conferences WHERE 1=1"
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
        return [_row_to_conference(r) for r in conn.execute(q, params).fetchall()]


def get_conference(db_path: Path, cid: str) -> Conference | None:
    with get_db(db_path) as conn:
        r = conn.execute("SELECT * FROM conferences WHERE id=?", (cid,)).fetchone()
    return _row_to_conference(r) if r else None


def update_conference(
    db_path: Path,
    cid: str,
    name: str | None = None,
    venue: str | None = None,
    location: str | None = None,
    deadline: str | None = None,
    submission_date: str | None = None,
    decision_date: str | None = None,
    status: str | None = None,
    presentation_type: str | None = None,
    travel_funding: float | None = None,
    travel_notes: str | None = None,
    url: str | None = None,
    notes: str | None = None,
    project_id: str | None = None,
    publication_id: str | None = None,
) -> Conference | None:
    updates = {}
    if name is not None:
        updates["name"] = name
    if venue is not None:
        updates["venue"] = venue
    if location is not None:
        updates["location"] = location
    if deadline is not None:
        updates["deadline"] = deadline
    if submission_date is not None:
        updates["submission_date"] = submission_date
    if decision_date is not None:
        updates["decision_date"] = decision_date
    if status is not None:
        updates["status"] = status
    if presentation_type is not None:
        updates["presentation_type"] = presentation_type
    if travel_funding is not None:
        updates["travel_funding"] = travel_funding
    if travel_notes is not None:
        updates["travel_notes"] = travel_notes
    if url is not None:
        updates["url"] = url
    if notes is not None:
        updates["notes"] = notes
    if project_id is not None:
        updates["project_id"] = project_id
    if publication_id is not None:
        updates["publication_id"] = publication_id
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
