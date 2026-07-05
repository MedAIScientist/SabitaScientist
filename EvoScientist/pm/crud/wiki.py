from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import LabWikiPage


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", title.lower().replace(" ", "-"))[:80]


def create_page(
    db_path: Path,
    lab_id: str,
    title: str,
    content: str = "",
    tags: list[str] | None = None,
    created_by: str = "agent",
) -> LabWikiPage:
    pid, now = uuid.uuid4().hex, datetime.now(UTC).isoformat()
    slug = _slugify(title)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO lab_wiki_pages (id,lab_id,title,slug,content,tags,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                pid,
                lab_id,
                title,
                slug,
                content,
                json.dumps(tags or []),
                created_by,
                now,
                now,
            ),
        )
    return LabWikiPage(
        id=pid,
        lab_id=lab_id,
        title=title,
        slug=slug,
        content=content,
        tags=tags or [],
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def list_pages(
    db_path: Path, lab_id: str, offset: int = 0, limit: int = 50
) -> list[LabWikiPage]:
    with get_db(db_path) as conn:
        return [
            LabWikiPage(
                id=r["id"],
                lab_id=r["lab_id"],
                title=r["title"],
                slug=r["slug"],
                content=r["content"],
                tags=json.loads(r["tags"]) if isinstance(r["tags"], str) else [],
                created_by=r["created_by"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in conn.execute(
                "SELECT * FROM lab_wiki_pages WHERE lab_id=? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (lab_id, limit, offset),
            ).fetchall()
        ]


def get_page(db_path: Path, page_id: str) -> LabWikiPage | None:
    with get_db(db_path) as conn:
        r = conn.execute(
            "SELECT * FROM lab_wiki_pages WHERE id=?", (page_id,)
        ).fetchone()
    return (
        LabWikiPage(
            id=r["id"],
            lab_id=r["lab_id"],
            title=r["title"],
            slug=r["slug"],
            content=r["content"],
            tags=json.loads(r["tags"]) if isinstance(r["tags"], str) else [],
            created_by=r["created_by"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        if r
        else None
    )


def get_page_by_slug(db_path: Path, lab_id: str, slug: str) -> LabWikiPage | None:
    with get_db(db_path) as conn:
        r = conn.execute(
            "SELECT * FROM lab_wiki_pages WHERE lab_id=? AND slug=?", (lab_id, slug)
        ).fetchone()
    return (
        LabWikiPage(
            id=r["id"],
            lab_id=r["lab_id"],
            title=r["title"],
            slug=r["slug"],
            content=r["content"],
            tags=json.loads(r["tags"]) if isinstance(r["tags"], str) else [],
            created_by=r["created_by"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        if r
        else None
    )


def update_page(
    db_path: Path,
    page_id: str,
    content: str | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
) -> LabWikiPage | None:
    now = datetime.now(UTC).isoformat()
    updates = {}
    if content is not None:
        updates["content"] = content
    if title is not None:
        updates["title"] = title
        updates["slug"] = _slugify(title)
    if tags is not None:
        updates["tags"] = json.dumps(tags)
    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        with get_db(db_path) as conn:
            conn.execute(
                f"UPDATE lab_wiki_pages SET {set_clause}, updated_at=? WHERE id=?",
                [*updates.values(), now, page_id],
            )
    return get_page(db_path, page_id)


def delete_page(db_path: Path, page_id: str) -> bool:
    with get_db(db_path) as conn:
        return (
            conn.execute("DELETE FROM lab_wiki_pages WHERE id=?", (page_id,)).rowcount
            > 0
        )
