"""CRUD operations for imaging datasets — the governance record of one delivered cohort.

A dataset is a database row BEFORE it is a bucket (v2 storage model, 20 Aug 2026):
Curator refuses a C-MOVE without an 'approved' dataset id, and the manifest that
lands in the bucket is a copy of this row, never the source of truth. The status
machine is strictly forward:

    draft -> pi_approved -> approved -> delivering -> sealed
                                     \\-> expired | revoked  (from any post-approval state)

Every mutation bumps ``generation`` so the desired-state push to platform-control
is monotonic — a replayed or out-of-order push can never regress cluster grants.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Dataset, DatasetGrant

_DATASET_COLS = (
    "id,name,purpose,lab_id,requested_by,modality,accession_list,estimated_bytes,"
    "status,pi_approved_by,pi_approved_at,admin_approved_by,admin_approved_at,"
    "retention_until,pepper_generation,bucket,sealed_at,content_root_sha256,"
    "renders,generation,created_at,updated_at"
)


def _row_to_dataset(r) -> Dataset:
    return Dataset(
        id=r["id"],
        name=r["name"],
        purpose=r["purpose"],
        lab_id=r["lab_id"],
        requested_by=r["requested_by"],
        modality=r["modality"],
        accession_list=json.loads(r["accession_list"] or "[]"),
        estimated_bytes=r["estimated_bytes"],
        status=r["status"],
        pi_approved_by=r["pi_approved_by"],
        pi_approved_at=r["pi_approved_at"],
        admin_approved_by=r["admin_approved_by"],
        admin_approved_at=r["admin_approved_at"],
        retention_until=r["retention_until"],
        pepper_generation=r["pepper_generation"],
        bucket=r["bucket"],
        sealed_at=r["sealed_at"],
        content_root_sha256=r["content_root_sha256"],
        renders=bool(r["renders"]),
        generation=r["generation"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _row_to_grant(r) -> DatasetGrant:
    return DatasetGrant(
        id=r["id"],
        dataset_id=r["dataset_id"],
        project_id=r["project_id"],
        granted_by=r["granted_by"],
        admin_approved_by=r["admin_approved_by"],
        admin_approved_at=r["admin_approved_at"],
        granted_at=r["granted_at"],
        expires_at=r["expires_at"],
        revoked_at=r["revoked_at"],
        revoked_by=r["revoked_by"],
        cvat_project_id=(r["cvat_project_id"] if "cvat_project_id" in r.keys() else None),
        task_size=(r["task_size"] if "task_size" in r.keys() else None),
    )


def create_dataset(
    db_path: Path,
    name: str,
    purpose: str,
    lab_id: str,
    requested_by: str,
    modality: str | None = None,
    accession_list: list[str] | None = None,
    estimated_bytes: int | None = None,
    renders: bool = True,
) -> Dataset:
    did = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO datasets (id,name,purpose,lab_id,requested_by,modality,"
            "accession_list,estimated_bytes,renders,status,generation,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,'draft',0,?,?)",
            (
                did,
                name,
                purpose,
                lab_id,
                requested_by,
                modality,
                json.dumps(accession_list or []),
                estimated_bytes,
                1 if renders else 0,
                now,
                now,
            ),
        )
    return get_dataset(db_path, did)


def get_dataset(db_path: Path, dataset_id: str) -> Dataset | None:
    with get_db(db_path) as conn:
        r = conn.execute(
            f"SELECT {_DATASET_COLS} FROM datasets WHERE id=?", (dataset_id,)
        ).fetchone()
    return _row_to_dataset(r) if r else None


def list_datasets(
    db_path: Path,
    lab_ids: list[str] | None = None,
    status: str | None = None,
) -> list[Dataset]:
    """All datasets, or only those in the given labs / with the given status."""
    query = f"SELECT {_DATASET_COLS} FROM datasets"
    where, params = [], []
    if lab_ids is not None:
        if not lab_ids:
            return []
        where.append(f"lab_id IN ({','.join('?' * len(lab_ids))})")
        params.extend(lab_ids)
    if status is not None:
        where.append("status=?")
        params.append(status)
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY created_at DESC"
    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dataset(r) for r in rows]


def update_dataset(db_path: Path, dataset_id: str, **fields) -> Dataset | None:
    """Set the given columns, bump generation and updated_at in one transaction.

    Generation moves on EVERY mutation, not only status changes, so the desired-
    state push is monotonic even for metadata-only edits.
    """
    allowed = {
        "status",
        "pi_approved_by",
        "pi_approved_at",
        "admin_approved_by",
        "admin_approved_at",
        "retention_until",
        "bucket",
        "sealed_at",
        "content_root_sha256",
        "estimated_bytes",
        "accession_list",
        "modality",
        "name",
        "purpose",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if "accession_list" in updates:
        updates["accession_list"] = json.dumps(updates["accession_list"])
    if not updates:
        return get_dataset(db_path, dataset_id)
    now = datetime.now(UTC).isoformat()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_db(db_path) as conn:
        conn.execute(
            f"UPDATE datasets SET {set_clause}, generation=generation+1, updated_at=? "
            "WHERE id=?",
            [*updates.values(), now, dataset_id],
        )
    return get_dataset(db_path, dataset_id)


def bump_generation(db_path: Path, dataset_id: str) -> int:
    """Bump and return the generation — used when a GRANT changes but the
    dataset row itself does not (the push document covers both)."""
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE datasets SET generation=generation+1, updated_at=? WHERE id=?",
            (now, dataset_id),
        )
        r = conn.execute(
            "SELECT generation FROM datasets WHERE id=?", (dataset_id,)
        ).fetchone()
    return r["generation"] if r else 0


# ── IRB links ─────────────────────────────────────────────────────────────────


def link_irb(db_path: Path, dataset_id: str, irb_id: str) -> None:
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO dataset_irbs (dataset_id, irb_id) VALUES (?,?)",
            (dataset_id, irb_id),
        )


def list_irb_ids(db_path: Path, dataset_id: str) -> list[str]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT irb_id FROM dataset_irbs WHERE dataset_id=?", (dataset_id,)
        ).fetchall()
    return [r["irb_id"] for r in rows]


# ── Grants ────────────────────────────────────────────────────────────────────


def create_grant(
    db_path: Path,
    dataset_id: str,
    project_id: str,
    granted_by: str,
    expires_at: str | None = None,
    cvat_project_id: int | None = None,
    task_size: int | None = None,
) -> DatasetGrant:
    gid = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO dataset_grants (id,dataset_id,project_id,granted_by,"
            "granted_at,expires_at,cvat_project_id,task_size) VALUES (?,?,?,?,?,?,?,?)",
            (gid, dataset_id, project_id, granted_by, now, expires_at,
             cvat_project_id, task_size),
        )
    return get_grant(db_path, gid)


def get_grant(db_path: Path, grant_id: str) -> DatasetGrant | None:
    with get_db(db_path) as conn:
        r = conn.execute(
            "SELECT * FROM dataset_grants WHERE id=?", (grant_id,)
        ).fetchone()
    return _row_to_grant(r) if r else None


def list_grants(db_path: Path, dataset_id: str) -> list[DatasetGrant]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM dataset_grants WHERE dataset_id=? ORDER BY granted_at",
            (dataset_id,),
        ).fetchall()
    return [_row_to_grant(r) for r in rows]


def approve_grant(db_path: Path, grant_id: str, admin_id: str) -> DatasetGrant | None:
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE dataset_grants SET admin_approved_by=?, admin_approved_at=? "
            "WHERE id=? AND revoked_at IS NULL",
            (admin_id, now, grant_id),
        )
    return get_grant(db_path, grant_id)


def revoke_grant(db_path: Path, grant_id: str, revoked_by: str) -> DatasetGrant | None:
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE dataset_grants SET revoked_at=?, revoked_by=? "
            "WHERE id=? AND revoked_at IS NULL",
            (now, revoked_by, grant_id),
        )
    return get_grant(db_path, grant_id)


def project_reference_counts(db_path: Path, project_id: str) -> dict[str, int]:
    """How many governance rows reference this project — the delete guard's input."""
    with get_db(db_path) as conn:
        return {
            "irb_approvals": conn.execute(
                "SELECT count(*) FROM irb_approvals WHERE project_id=?", (project_id,)
            ).fetchone()[0],
            "deid_pipeline_runs": conn.execute(
                "SELECT count(*) FROM deid_pipeline_runs WHERE project_id=?",
                (project_id,),
            ).fetchone()[0],
            "cvat_projects": conn.execute(
                "SELECT count(*) FROM cvat_projects WHERE project_id=?", (project_id,)
            ).fetchone()[0],
            "dataset_grants": conn.execute(
                "SELECT count(*) FROM dataset_grants WHERE project_id=?", (project_id,)
            ).fetchone()[0],
        }
