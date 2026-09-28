"""CRUD operations for Grant entities."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Grant


def _row_to_grant(r) -> Grant:
    return Grant(
        id=r["id"],
        title=r["title"],
        funder=r["funder"],
        amount_requested=r["amount_requested"],
        amount_awarded=r["amount_awarded"],
        currency=r["currency"],
        status=r["status"],
        submitted_at=r["submitted_at"],
        awarded_at=r["awarded_at"],
        start_date=r["start_date"],
        end_date=r["end_date"],
        description=r["description"],
        pi_id=r["pi_id"],
        pi_username=r["pi_username"] if "pi_username" in r.keys() else None,
        project_id=r["project_id"],
        lab_id=r["lab_id"],
        created_by=r["created_by"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


# Every read joins the PI's username: the UI shows a name, not a uuid.
_SELECT_GRANT = """SELECT g.*, u.username AS pi_username
                   FROM grants g LEFT JOIN users u ON u.id = g.pi_id"""


def create_grant(
    db_path: Path,
    title: str,
    funder: str,
    created_by: str,
    lab_id: str | None = None,
    project_id: str | None = None,
    amount_requested: float | None = None,
    amount_awarded: float | None = None,
    currency: str = "TRY",
    status: str = "draft",
    submitted_at: str | None = None,
    awarded_at: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    description: str | None = None,
    pi_id: str | None = None,
) -> Grant:
    gid = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO grants (id,lab_id,project_id,title,funder,amount_requested,amount_awarded,currency,status,submitted_at,awarded_at,start_date,end_date,description,pi_id,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                gid,
                lab_id,
                project_id,
                title,
                funder,
                amount_requested,
                amount_awarded,
                currency,
                status,
                submitted_at,
                awarded_at,
                start_date,
                end_date,
                description,
                pi_id,
                created_by,
                now,
                now,
            ),
        )
    # Re-read the row so the PI's joined username comes back too.
    created = get_grant(db_path, gid)
    assert created is not None  # just inserted in the same call
    return created


# Sort keys a client may ask for, mapped to a safe ORDER BY expression. The key
# arrives from a query string, so it is looked up rather than interpolated.
_SORT_EXPRESSIONS = {
    "created_at": "g.created_at ASC",
    "-created_at": "g.created_at DESC",
    "title": "g.title COLLATE NOCASE ASC",
    "-title": "g.title COLLATE NOCASE DESC",
    "end_date": "(g.end_date IS NULL), g.end_date ASC",
    "-end_date": "(g.end_date IS NULL), g.end_date DESC",
    "amount_awarded": "(g.amount_awarded IS NULL), g.amount_awarded ASC",
    "-amount_awarded": "(g.amount_awarded IS NULL), g.amount_awarded DESC",
}

DEFAULT_SORT = "-created_at"


def list_grants(
    db_path: Path,
    lab_id: str | None = None,
    project_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
    q: str | None = None,
    sort: str = DEFAULT_SORT,
) -> list[Grant]:
    query = f"{_SELECT_GRANT} WHERE 1=1"
    params: list = []
    if lab_id:
        query += " AND g.lab_id=?"
        params.append(lab_id)
    if project_id:
        query += " AND g.project_id=?"
        params.append(project_id)
    if status:
        query += " AND g.status=?"
        params.append(status)
    if q:
        # Free-text over the fields a person actually scans a grant list by.
        like = f"%{q.strip()}%"
        query += " AND (g.title LIKE ? OR g.funder LIKE ? OR g.description LIKE ?)"
        params.extend([like, like, like])
    query += f" ORDER BY {_SORT_EXPRESSIONS.get(sort, _SORT_EXPRESSIONS[DEFAULT_SORT])}"
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_db(db_path) as conn:
        return [_row_to_grant(r) for r in conn.execute(query, params).fetchall()]


def get_grant(db_path: Path, gid: str) -> Grant | None:
    with get_db(db_path) as conn:
        r = conn.execute(f"{_SELECT_GRANT} WHERE g.id=?", (gid,)).fetchone()
    return _row_to_grant(r) if r else None


def update_grant(
    db_path: Path,
    gid: str,
    title: str | None = None,
    funder: str | None = None,
    amount_requested: float | None = None,
    amount_awarded: float | None = None,
    currency: str | None = None,
    status: str | None = None,
    submitted_at: str | None = None,
    awarded_at: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    description: str | None = None,
    pi_id: str | None = None,
    lab_id: str | None = None,
    project_id: str | None = None,
) -> Grant | None:
    updates = {}
    if title is not None:
        updates["title"] = title
    if funder is not None:
        updates["funder"] = funder
    if amount_requested is not None:
        updates["amount_requested"] = amount_requested
    if amount_awarded is not None:
        updates["amount_awarded"] = amount_awarded
    if currency is not None:
        updates["currency"] = currency
    if status is not None:
        updates["status"] = status
    if submitted_at is not None:
        updates["submitted_at"] = submitted_at
    if awarded_at is not None:
        updates["awarded_at"] = awarded_at
    if start_date is not None:
        updates["start_date"] = start_date
    if end_date is not None:
        updates["end_date"] = end_date
    if description is not None:
        updates["description"] = description
    if pi_id is not None:
        updates["pi_id"] = pi_id
    if lab_id is not None:
        updates["lab_id"] = lab_id
    if project_id is not None:
        updates["project_id"] = project_id
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
