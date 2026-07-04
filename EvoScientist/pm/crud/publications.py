"""CRUD operations for Publication, Version, and Review entities."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Publication, PublicationReview, PublicationVersion


def create_publication(
    db_path: Path,
    title: str,
    created_by: str,
    project_id: str | None = None,
    venue: str | None = None,
    venue_type: str = "journal",
    authors: list[dict] | None = None,
    abstract: str | None = None,
    doi: str | None = None,
    url: str | None = None,
) -> Publication:
    pub_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    authors_json = json.dumps(authors or [])
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO publications
               (id, project_id, title, venue, venue_type, authors, status,
                doi, url, abstract, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)""",
            (pub_id, project_id, title, venue, venue_type, authors_json,
             doi, url, abstract, created_by, now, now),
        )
    return Publication(
        id=pub_id,
        project_id=project_id,
        title=title,
        venue=venue,
        venue_type=venue_type,
        authors=authors or [],
        status="draft",
        doi=doi,
        url=url,
        abstract=abstract,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def get_publication(db_path: Path, pub_id: str) -> Publication | None:
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM publications WHERE id = ?", (pub_id,)).fetchone()
    return _row_to_publication(row) if row else None


def list_publications(
    db_path: Path,
    project_id: str | None = None,
    status: str | None = None,
) -> list[Publication]:
    query = "SELECT * FROM publications WHERE 1=1"
    params: list = []
    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY updated_at DESC"
    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_publication(r) for r in rows]


def update_publication(
    db_path: Path,
    pub_id: str,
    **kwargs,
) -> Publication:
    pub = get_publication(db_path, pub_id)
    if pub is None:
        raise ValueError(f"Publication {pub_id!r} not found")
    allowed = {"title", "venue", "venue_type", "authors", "abstract", "doi", "url", "status",
               "submitted_at", "accepted_at", "published_at"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return pub
    now = datetime.now(UTC).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = [*list(updates.values()), now, pub_id]
    with get_db(db_path) as conn:
        conn.execute(
            f"UPDATE publications SET {set_clause}, updated_at = ? WHERE id = ?", values
        )
    return get_publication(db_path, pub_id)


def delete_publication(db_path: Path, pub_id: str) -> bool:
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM publications WHERE id = ?", (pub_id,))
    return cur.rowcount > 0


def create_version(
    db_path: Path,
    publication_id: str,
    created_by: str,
    notes: str | None = None,
) -> PublicationVersion:
    ver_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        max_ver = conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM publication_versions WHERE publication_id = ?",
            (publication_id,),
        ).fetchone()[0]
        new_ver = max_ver + 1
        conn.execute(
            """INSERT INTO publication_versions
               (id, publication_id, version, notes, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ver_id, publication_id, new_ver, notes, created_by, now),
        )
    return PublicationVersion(
        id=ver_id,
        publication_id=publication_id,
        version=new_ver,
        notes=notes,
        created_by=created_by,
        created_at=now,
    )


def list_versions(db_path: Path, publication_id: str) -> list[PublicationVersion]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM publication_versions WHERE publication_id = ? ORDER BY version DESC",
            (publication_id,),
        ).fetchall()
    return [
        PublicationVersion(
            id=r["id"], publication_id=r["publication_id"],
            version=r["version"], file_path=r["file_path"],
            notes=r["notes"], created_by=r["created_by"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


def create_review(
    db_path: Path,
    publication_id: str,
    round: int = 1,
    reviewer_name: str | None = None,
    comments: str | None = None,
    decision: str | None = None,
) -> PublicationReview:
    rev_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO publication_reviews
               (id, publication_id, reviewer_name, comments, decision, round, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rev_id, publication_id, reviewer_name, comments, decision, round, now),
        )
    return PublicationReview(
        id=rev_id, publication_id=publication_id,
        reviewer_name=reviewer_name, comments=comments,
        decision=decision, round=round, created_at=now,
    )


def list_reviews(db_path: Path, publication_id: str) -> list[PublicationReview]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM publication_reviews WHERE publication_id = ? ORDER BY round DESC, created_at DESC",
            (publication_id,),
        ).fetchall()
    return [
        PublicationReview(
            id=r["id"], publication_id=r["publication_id"],
            reviewer_name=r["reviewer_name"], comments=r["comments"],
            decision=r["decision"], round=r["round"], created_at=r["created_at"],
        )
        for r in rows
    ]


def _row_to_publication(row) -> Publication:
    return Publication(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        venue=row["venue"],
        venue_type=row["venue_type"],
        authors=json.loads(row["authors"]) if isinstance(row["authors"], str) else (row["authors"] or []),
        status=row["status"],
        doi=row["doi"],
        url=row["url"],
        abstract=row["abstract"],
        submitted_at=row["submitted_at"],
        accepted_at=row["accepted_at"],
        published_at=row["published_at"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
