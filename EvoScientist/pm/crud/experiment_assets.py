"""CRUD for the data assets an experiment is traced to.

An experiment is where data processing and imaging analysis actually happen, but
the assets involved — imaging cohorts, de-identification runs, annotation and
segmentation projects, sandboxes — belong to projects or labs. This link table is
what lets one experiment cite them without changing who owns them.

``asset_id`` carries no foreign key because the target table varies by
``asset_type``; existence is validated on link, and each asset's own delete route
calls :func:`clear_asset_links` so links cannot outlive their asset.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import EXPERIMENT_ASSET_TYPES, ExperimentAsset

# asset_type -> (table, has project_id). datasets are lab-owned and reach a
# project through dataset_grants instead, which is checked separately.
_ASSET_TABLES: dict[str, tuple[str, bool]] = {
    "dataset": ("datasets", False),
    "pipeline_run": ("deid_pipeline_runs", True),
    "cvat_project": ("cvat_projects", True),
    "webknossos_dataset": ("webknossos_datasets", True),
    "sandbox": ("sandboxes", True),
}


def _spec(asset_type: str) -> tuple[str, bool]:
    if asset_type not in _ASSET_TABLES:
        raise ValueError(f"Unknown asset type {asset_type!r}")
    return _ASSET_TABLES[asset_type]


def asset_exists(db_path: Path, asset_type: str, asset_id: str) -> bool:
    table, _ = _spec(asset_type)
    with get_db(db_path) as conn:
        return (
            conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (asset_id,)).fetchone()
            is not None
        )


def asset_project_id(db_path: Path, asset_type: str, asset_id: str) -> str | None:
    """The owning project, or None for a dataset (which belongs to a lab)."""
    table, project_scoped = _spec(asset_type)
    if not project_scoped:
        return None
    with get_db(db_path) as conn:
        row = conn.execute(
            f"SELECT project_id FROM {table} WHERE id=?", (asset_id,)
        ).fetchone()
    return row["project_id"] if row else None


def dataset_available_to_project(
    db_path: Path, dataset_id: str, project_id: str
) -> bool:
    """Whether an approved, unrevoked, unexpired grant lets this project use it.

    A proposed grant grants nothing anywhere until a platform admin approves it,
    so admin_approved_at must be set — otherwise a mere request would be enough to
    cite a cohort.
    """
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT 1 FROM dataset_grants
               WHERE dataset_id=? AND project_id=?
                 AND admin_approved_at IS NOT NULL
                 AND revoked_at IS NULL
                 AND (expires_at IS NULL OR expires_at > ?)
               LIMIT 1""",
            (dataset_id, project_id, datetime.now(UTC).isoformat()),
        ).fetchone()
    return row is not None


def link_asset(
    db_path: Path,
    experiment_id: str,
    asset_type: str,
    asset_id: str,
    linked_by: str,
    role: str = "input",
    note: str | None = None,
) -> ExperimentAsset:
    """Link an asset to an experiment, replacing the role if already linked."""
    _spec(asset_type)
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO experiment_assets
               (experiment_id, asset_type, asset_id, role, note, linked_at, linked_by)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(experiment_id, asset_type, asset_id)
               DO UPDATE SET role=excluded.role, note=excluded.note""",
            (experiment_id, asset_type, asset_id, role, note, now, linked_by),
        )
    return ExperimentAsset(
        experiment_id=experiment_id,
        asset_type=asset_type,
        asset_id=asset_id,
        role=role,
        note=note,
        linked_at=now,
        linked_by=linked_by,
    )


def unlink_asset(
    db_path: Path, experiment_id: str, asset_type: str, asset_id: str
) -> bool:
    with get_db(db_path) as conn:
        return (
            conn.execute(
                """DELETE FROM experiment_assets
                   WHERE experiment_id=? AND asset_type=? AND asset_id=?""",
                (experiment_id, asset_type, asset_id),
            ).rowcount
            > 0
        )


def clear_asset_links(db_path: Path, asset_type: str, asset_id: str) -> int:
    """Drop every link pointing at one asset. Called by the asset delete routes."""
    _spec(asset_type)
    with get_db(db_path) as conn:
        return conn.execute(
            "DELETE FROM experiment_assets WHERE asset_type=? AND asset_id=?",
            (asset_type, asset_id),
        ).rowcount


def _labels(db_path: Path, rows: list) -> dict[tuple[str, str], tuple[str, str | None]]:
    """Resolve display labels for the assets in the given link rows.

    One query per asset type present rather than one per row, so a lineage list
    costs at most five queries regardless of its length.
    """
    by_type: dict[str, list[str]] = {}
    for row in rows:
        by_type.setdefault(row["asset_type"], []).append(row["asset_id"])

    resolved: dict[tuple[str, str], tuple[str, str | None]] = {}

    def query(sql: str, ids: list[str]):
        placeholders = ",".join("?" * len(ids))
        with get_db(db_path) as conn:
            return conn.execute(sql.format(ph=placeholders), ids).fetchall()

    if ids := by_type.get("dataset"):
        for r in query(
            "SELECT id, name, modality, status FROM datasets WHERE id IN ({ph})", ids
        ):
            detail = " · ".join(x for x in (r["modality"], r["status"]) if x)
            resolved[("dataset", r["id"])] = (r["name"], detail or None)

    if ids := by_type.get("pipeline_run"):
        for r in query(
            """SELECT run.id, run.status, p.name AS pipeline_name
               FROM deid_pipeline_runs run
               LEFT JOIN deid_pipelines p ON p.id = run.pipeline_id
               WHERE run.id IN ({ph})""",
            ids,
        ):
            label = r["pipeline_name"] or "de-identification run"
            resolved[("pipeline_run", r["id"])] = (label, r["status"])

    if ids := by_type.get("cvat_project"):
        for r in query(
            "SELECT id, name, status, num_images FROM cvat_projects WHERE id IN ({ph})",
            ids,
        ):
            detail = " · ".join(
                x
                for x in (
                    r["status"],
                    f"{r['num_images']} images" if r["num_images"] else None,
                )
                if x
            )
            resolved[("cvat_project", r["id"])] = (r["name"], detail or None)

    if ids := by_type.get("webknossos_dataset"):
        for r in query(
            "SELECT id, name, status FROM webknossos_datasets WHERE id IN ({ph})", ids
        ):
            resolved[("webknossos_dataset", r["id"])] = (r["name"], r["status"])

    if ids := by_type.get("sandbox"):
        for r in query(
            "SELECT id, name, status FROM sandboxes WHERE id IN ({ph})", ids
        ):
            resolved[("sandbox", r["id"])] = (r["name"], r["status"])

    return resolved


def list_assets(db_path: Path, experiment_id: str) -> list[ExperimentAsset]:
    """Return an experiment's linked assets, inputs first, with labels resolved."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM experiment_assets WHERE experiment_id=?
               ORDER BY CASE role
                          WHEN 'input' THEN 0 WHEN 'processing' THEN 1
                          WHEN 'output' THEN 2 ELSE 3 END,
                        linked_at""",
            (experiment_id,),
        ).fetchall()
    if not rows:
        return []

    labels = _labels(db_path, rows)
    return [
        ExperimentAsset(
            experiment_id=r["experiment_id"],
            asset_type=r["asset_type"],
            asset_id=r["asset_id"],
            role=r["role"],
            note=r["note"],
            linked_at=r["linked_at"],
            linked_by=r["linked_by"],
            label=labels.get((r["asset_type"], r["asset_id"]), (None, None))[0],
            detail=labels.get((r["asset_type"], r["asset_id"]), (None, None))[1],
        )
        for r in rows
    ]


def count_assets_by_experiment(
    db_path: Path, experiment_ids: list[str]
) -> dict[str, int]:
    """Link counts for many experiments at once, for list/card badges."""
    if not experiment_ids:
        return {}
    placeholders = ",".join("?" * len(experiment_ids))
    with get_db(db_path) as conn:
        rows = conn.execute(
            f"""SELECT experiment_id, COUNT(*) AS n FROM experiment_assets
                WHERE experiment_id IN ({placeholders})
                GROUP BY experiment_id""",
            experiment_ids,
        ).fetchall()
    return {r["experiment_id"]: r["n"] for r in rows}


def list_projects_with_asset(
    db_path: Path, asset_type: str, asset_id: str
) -> list[str]:
    """Project ids reachable from the experiments that cite this asset."""
    _spec(asset_type)
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT DISTINCT e.project_id
               FROM experiment_assets a JOIN experiments e ON e.id = a.experiment_id
               WHERE a.asset_type=? AND a.asset_id=?""",
            (asset_type, asset_id),
        ).fetchall()
    return [r["project_id"] for r in rows]


assert set(EXPERIMENT_ASSET_TYPES) == set(_ASSET_TABLES), (
    "models.EXPERIMENT_ASSET_TYPES and the asset table map must stay in step"
)
