"""CRUD for de-identification pipelines and runs."""

from __future__ import annotations

from pathlib import Path

from ..db import get_db
from ..models import DeIDPipeline, DeIDPipelineRun

_COLUMNS_P = "id, project_id, name, description, pipeline_type, config_json, created_by, created_at, updated_at"
_COLUMNS_R = "id, pipeline_id, project_id, irb_id, input_location, output_location, status, input_size_bytes, output_size_bytes, records_processed, phi_fields_removed, verification_status, verification_notes, error, started_at, completed_at, created_by, created_at"


def _row_to_pipeline(r: dict) -> DeIDPipeline:
    return DeIDPipeline(
        id=r["id"],
        project_id=r["project_id"],
        name=r["name"],
        description=r.get("description"),
        pipeline_type=r["pipeline_type"],
        config_json=r["config_json"],
        created_by=r["created_by"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _row_to_run(r: dict) -> DeIDPipelineRun:
    return DeIDPipelineRun(
        id=r["id"],
        pipeline_id=r["pipeline_id"],
        project_id=r["project_id"],
        irb_id=r.get("irb_id"),
        input_location=r["input_location"],
        output_location=r["output_location"],
        status=r["status"],
        input_size_bytes=r.get("input_size_bytes"),
        output_size_bytes=r.get("output_size_bytes"),
        records_processed=r.get("records_processed"),
        phi_fields_removed=r.get("phi_fields_removed", "[]"),
        verification_status=r.get("verification_status"),
        verification_notes=r.get("verification_notes"),
        error=r.get("error"),
        started_at=r.get("started_at"),
        completed_at=r.get("completed_at"),
        created_by=r["created_by"],
        created_at=r["created_at"],
    )


def create_pipeline(
    db_path: str | Path,
    project_id: str,
    name: str,
    pipeline_type: str,
    created_by: str,
    description: str | None = None,
    config_json: str = "{}",
) -> DeIDPipeline:
    import uuid

    pid = str(uuid.uuid4())
    now = __import__("datetime").datetime.utcnow().isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            f"INSERT INTO deid_pipelines ({_COLUMNS_P}) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                pid,
                project_id,
                name,
                description,
                pipeline_type,
                config_json,
                created_by,
                now,
                now,
            ),
        )
        return get_pipeline(db_path, pid)


def get_pipeline(db_path: str | Path, pipeline_id: str) -> DeIDPipeline | None:
    with get_db(db_path) as conn:
        r = conn.execute(
            "SELECT * FROM deid_pipelines WHERE id = ?", (pipeline_id,)
        ).fetchone()
        return _row_to_pipeline(r) if r else None


def list_pipelines(db_path: str | Path, project_id: str) -> list[DeIDPipeline]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM deid_pipelines WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
        return [_row_to_pipeline(r) for r in rows]


def update_pipeline(db_path: str | Path, pipeline_id: str, **kw) -> DeIDPipeline | None:
    now = __import__("datetime").datetime.utcnow().isoformat()
    sets = {k: v for k, v in kw.items() if v is not None}
    if not sets:
        return get_pipeline(db_path, pipeline_id)
    sets["updated_at"] = now
    clause = ", ".join(f"{k} = ?" for k in sets)
    vals = [*list(sets.values()), pipeline_id]
    with get_db(db_path) as conn:
        conn.execute(f"UPDATE deid_pipelines SET {clause} WHERE id = ?", vals)
        return get_pipeline(db_path, pipeline_id)


def delete_pipeline(db_path: str | Path, pipeline_id: str) -> bool:
    with get_db(db_path) as conn:
        c = conn.execute("DELETE FROM deid_pipelines WHERE id = ?", (pipeline_id,))
        return c.rowcount > 0


def create_run(
    db_path: str | Path,
    project_id: str,
    pipeline_id: str,
    input_location: str,
    output_location: str,
    created_by: str,
    irb_id: str | None = None,
) -> DeIDPipelineRun:
    import uuid

    rid = str(uuid.uuid4())
    now = __import__("datetime").datetime.utcnow().isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            f"INSERT INTO deid_pipeline_runs ({_COLUMNS_R}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rid,
                pipeline_id,
                project_id,
                irb_id,
                input_location,
                output_location,
                "pending",
                None,
                None,
                None,
                "[]",
                None,
                None,
                None,
                None,
                None,
                created_by,
                now,
            ),
        )
        return get_run(db_path, rid)


def get_run(db_path: str | Path, run_id: str) -> DeIDPipelineRun | None:
    with get_db(db_path) as conn:
        r = conn.execute(
            "SELECT * FROM deid_pipeline_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return _row_to_run(r) if r else None


def list_runs(db_path: str | Path, pipeline_id: str) -> list[DeIDPipelineRun]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM deid_pipeline_runs WHERE pipeline_id = ? ORDER BY created_at DESC",
            (pipeline_id,),
        ).fetchall()
        return [_row_to_run(r) for r in rows]


def update_run(db_path: str | Path, run_id: str, **kw) -> DeIDPipelineRun | None:
    sets = {k: v for k, v in kw.items() if v is not None}
    if not sets:
        return get_run(db_path, run_id)
    clause = ", ".join(f"{k} = ?" for k in sets)
    vals = [*list(sets.values()), run_id]
    with get_db(db_path) as conn:
        conn.execute(f"UPDATE deid_pipeline_runs SET {clause} WHERE id = ?", vals)
        return get_run(db_path, run_id)
