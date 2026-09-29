"""CRUD for research sandboxes."""

from __future__ import annotations

from pathlib import Path

from ..db import get_db
from ..models import Sandbox

_COLUMNS = "id, project_id, irb_id, name, status, spec_json, network_rules_json, storage_quota_bytes, access_url, provisioned_at, expires_at, terminated_at, created_by, created_at, updated_at"


def _row_to_sandbox(r: dict) -> Sandbox:
    # get_db sets row_factory=sqlite3.Row, which supports r["col"] but has no
    # .get(); normalise to a dict so optional columns can be read defensively.
    r = dict(r)
    return Sandbox(
        id=r["id"],
        project_id=r["project_id"],
        irb_id=r.get("irb_id"),
        name=r["name"],
        status=r["status"],
        spec_json=r["spec_json"],
        network_rules_json=r["network_rules_json"],
        storage_quota_bytes=r.get("storage_quota_bytes"),
        access_url=r.get("access_url"),
        provisioned_at=r.get("provisioned_at"),
        expires_at=r.get("expires_at"),
        terminated_at=r.get("terminated_at"),
        created_by=r["created_by"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def create_sandbox(
    db_path: str | Path,
    project_id: str,
    name: str,
    created_by: str,
    spec_json: str = "{}",
    network_rules_json: str = "[]",
    irb_id: str | None = None,
    storage_quota_bytes: int | None = None,
    expires_at: str | None = None,
) -> Sandbox:
    import uuid

    sid = str(uuid.uuid4())
    now = __import__("datetime").datetime.utcnow().isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            f"INSERT INTO sandboxes ({_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                sid,
                project_id,
                irb_id,
                name,
                "provisioning",
                spec_json,
                network_rules_json,
                storage_quota_bytes,
                None,
                None,
                expires_at,
                None,
                created_by,
                now,
                now,
            ),
        )
    # Re-read AFTER the block commits: get_db commits on exit, so a read issued
    # inside it uses a second connection that cannot see this row yet.
    return get_sandbox(db_path, sid)


def get_sandbox(db_path: str | Path, sandbox_id: str) -> Sandbox | None:
    with get_db(db_path) as conn:
        r = conn.execute(
            "SELECT * FROM sandboxes WHERE id = ?", (sandbox_id,)
        ).fetchone()
        return _row_to_sandbox(r) if r else None


def list_sandboxes(db_path: str | Path, project_id: str) -> list[Sandbox]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM sandboxes WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
        return [_row_to_sandbox(r) for r in rows]


def update_sandbox(db_path: str | Path, sandbox_id: str, **kw) -> Sandbox | None:
    now = __import__("datetime").datetime.utcnow().isoformat()
    sets = {k: v for k, v in kw.items() if v is not None}
    if not sets:
        return get_sandbox(db_path, sandbox_id)
    sets["updated_at"] = now
    clause = ", ".join(f"{k} = ?" for k in sets)
    vals = [*list(sets.values()), sandbox_id]
    with get_db(db_path) as conn:
        conn.execute(f"UPDATE sandboxes SET {clause} WHERE id = ?", vals)
    return get_sandbox(db_path, sandbox_id)


def delete_sandbox(db_path: str | Path, sandbox_id: str) -> bool:
    with get_db(db_path) as conn:
        c = conn.execute("DELETE FROM sandboxes WHERE id = ?", (sandbox_id,))
        return c.rowcount > 0


def expire_sandboxes_by_irb(db_path: str | Path, irb_id: str) -> int:
    """Expire all active sandboxes linked to an IRB that has expired."""
    now = __import__("datetime").datetime.utcnow().isoformat()
    with get_db(db_path) as conn:
        c = conn.execute(
            "UPDATE sandboxes SET status = 'expired', updated_at = ? WHERE irb_id = ? AND status IN ('active','expiring')",
            (now, irb_id),
        )
        return c.rowcount
