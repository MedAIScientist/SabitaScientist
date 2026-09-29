"""CRUD for CVAT project links."""

from __future__ import annotations

from pathlib import Path

from ..db import get_db
from ..models import CVATProject


def _row_to_cvat(r: dict) -> CVATProject:
    return CVATProject(
        id=r["id"], project_id=r["project_id"], cvat_id=r["cvat_id"],
        name=r["name"], labels_json=r["labels_json"],
        status=r["status"], num_images=r["num_images"],
        num_annotations=r["num_annotations"],
        export_format=r["export_format"],
        export_key=r["export_key"],
        created_by=r["created_by"], created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def create_cvat_project(db_path: str | Path, project_id: str, cvat_id: int, name: str, created_by: str, labels_json: str = "[]") -> CVATProject:
    import uuid
    cid = str(uuid.uuid4())
    now = __import__("datetime").datetime.utcnow().isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO cvat_projects (id, project_id, cvat_id, name, labels_json, status, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (cid, project_id, cvat_id, name, labels_json, "created", created_by, now, now),
        )
    # Re-read AFTER the block commits: get_db commits on exit, so a read issued
    # inside it uses a second connection that cannot see this row yet.
    return get_cvat_project(db_path, cid)


def get_cvat_project(db_path: str | Path, cid: str) -> CVATProject | None:
    with get_db(db_path) as conn:
        r = conn.execute("SELECT * FROM cvat_projects WHERE id = ?", (cid,)).fetchone()
        return _row_to_cvat(r) if r else None


def list_cvat_projects(db_path: str | Path, project_id: str) -> list[CVATProject]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cvat_projects WHERE project_id = ? ORDER BY created_at DESC", (project_id,)
        ).fetchall()
        return [_row_to_cvat(r) for r in rows]


def update_cvat_project(db_path: str | Path, cid: str, **kw) -> CVATProject | None:
    now = __import__("datetime").datetime.utcnow().isoformat()
    sets = {k: v for k, v in kw.items() if v is not None}
    if not sets:
        return get_cvat_project(db_path, cid)
    sets["updated_at"] = now
    clause = ", ".join(f"{k} = ?" for k in sets)
    vals = [*sets.values(), cid]
    with get_db(db_path) as conn:
        conn.execute(f"UPDATE cvat_projects SET {clause} WHERE id = ?", vals)
    return get_cvat_project(db_path, cid)


def delete_cvat_project(db_path: str | Path, cid: str) -> bool:
    with get_db(db_path) as conn:
        c = conn.execute("DELETE FROM cvat_projects WHERE id = ?", (cid,))
        return c.rowcount > 0
