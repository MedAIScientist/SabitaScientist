"""CRUD for WebKnossos dataset links."""

from __future__ import annotations

from pathlib import Path

from ..db import get_db
from ..models import WebKnossosDataset


def _row_to_wk(r: dict) -> WebKnossosDataset:
    # get_db sets row_factory=sqlite3.Row, which supports r["col"] but has no
    # .get(); normalise to a dict so optional columns can be read defensively.
    r = dict(r)
    return WebKnossosDataset(
        id=r["id"], project_id=r["project_id"], wk_id=r.get("wk_id"),
        name=r["name"], directory_name=r["directory_name"], status=r["status"],
        voxel_count=r.get("voxel_count"),
        segmentation_status=r.get("segmentation_status", "pending"),
        num_skeletons=r.get("num_skeletons", 0),
        num_volumes=r.get("num_volumes", 0),
        created_by=r["created_by"], created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def create_wk_dataset(db_path: str | Path, project_id: str, name: str, directory_name: str, created_by: str, wk_id: str | None = None) -> WebKnossosDataset:
    import uuid
    wid = str(uuid.uuid4())
    now = __import__("datetime").datetime.utcnow().isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO webknossos_datasets (id, project_id, wk_id, name, directory_name, status, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (wid, project_id, wk_id, name, directory_name, "imported", created_by, now, now),
        )
    # Re-read AFTER the block commits: get_db commits on exit, so a read issued
    # inside it uses a second connection that cannot see this row yet.
    return get_wk_dataset(db_path, wid)


def get_wk_dataset(db_path: str | Path, wid: str) -> WebKnossosDataset | None:
    with get_db(db_path) as conn:
        r = conn.execute("SELECT * FROM webknossos_datasets WHERE id = ?", (wid,)).fetchone()
        return _row_to_wk(r) if r else None


def list_wk_datasets(db_path: str | Path, project_id: str) -> list[WebKnossosDataset]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM webknossos_datasets WHERE project_id = ? ORDER BY created_at DESC", (project_id,)
        ).fetchall()
        return [_row_to_wk(r) for r in rows]


def update_wk_dataset(db_path: str | Path, wid: str, **kw) -> WebKnossosDataset | None:
    now = __import__("datetime").datetime.utcnow().isoformat()
    sets = {k: v for k, v in kw.items() if v is not None}
    if not sets:
        return get_wk_dataset(db_path, wid)
    sets["updated_at"] = now
    clause = ", ".join(f"{k} = ?" for k in sets)
    vals = [*sets.values(), wid]
    with get_db(db_path) as conn:
        conn.execute(f"UPDATE webknossos_datasets SET {clause} WHERE id = ?", vals)
    return get_wk_dataset(db_path, wid)


def delete_wk_dataset(db_path: str | Path, wid: str) -> bool:
    with get_db(db_path) as conn:
        c = conn.execute("DELETE FROM webknossos_datasets WHERE id = ?", (wid,))
        return c.rowcount > 0
