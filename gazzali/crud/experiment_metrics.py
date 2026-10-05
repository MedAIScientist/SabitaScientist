"""CRUD operations for ExperimentMetric entities."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..metrics_csv import ParsedMetric
from ..models import ExperimentMetric


def create_metrics(
    db_path: Path,
    experiment_id: str,
    metrics: Iterable[ParsedMetric],
    recorded_by: str | None = None,
    source_attachment_id: str | None = None,
    source: str | None = None,
) -> list[ExperimentMetric]:
    """Insert parsed metrics for an experiment in one transaction."""
    source = source or _derive_source(source_attachment_id, recorded_by)
    now = datetime.now(UTC).isoformat()
    created = [
        ExperimentMetric(
            id=uuid.uuid4().hex,
            experiment_id=experiment_id,
            name=m.name,
            value=m.value,
            created_at=now,
            unit=m.unit,
            split=m.split,
            n=m.n,
            stderr=m.stderr,
            source_attachment_id=source_attachment_id,
            recorded_by=recorded_by,
            source=source,
        )
        for m in metrics
    ]
    if not created:
        return []
    with get_db(db_path) as conn:
        conn.executemany(
            """INSERT INTO experiment_metrics
               (id, experiment_id, name, value, unit, split, n, stderr,
                source_attachment_id, recorded_by, created_at, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    m.id,
                    m.experiment_id,
                    m.name,
                    m.value,
                    m.unit,
                    m.split,
                    m.n,
                    m.stderr,
                    m.source_attachment_id,
                    m.recorded_by,
                    m.created_at,
                    m.source,
                )
                for m in created
            ],
        )
    return created


def _derive_source(source_attachment_id: str | None, recorded_by: str | None) -> str:
    """Rows written before the source column: a file → csv, a person → manual, else an AI run."""
    if source_attachment_id:
        return "csv"
    return "manual" if recorded_by else "ai_run"


def delete_metrics_by_source(db_path: Path, experiment_id: str, source: str, split: str | None) -> int:
    """Remove one source's numbers for an experiment (e.g. before re-importing from CVAT)."""
    with get_db(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM experiment_metrics WHERE experiment_id = ? AND source = ? AND split IS ?",
            (experiment_id, source, split),
        )
    return cur.rowcount


def list_metrics(db_path: Path, experiment_id: str) -> list[ExperimentMetric]:
    """Return all metrics for an experiment, ordered by name then split."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM experiment_metrics WHERE experiment_id = ?
               ORDER BY name, split, created_at""",
            (experiment_id,),
        ).fetchall()
    return [_row_to_metric(r) for r in rows]


def delete_metric(db_path: Path, metric_id: str) -> bool:
    """Delete one metric. Returns True if it existed."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM experiment_metrics WHERE id = ?", (metric_id,))
    return cur.rowcount > 0


def delete_metrics_for_attachment(db_path: Path, attachment_id: str) -> int:
    """Delete metrics parsed from an attachment. Returns rows removed.

    Keeps the metrics table from outliving the file it was derived from.
    """
    with get_db(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM experiment_metrics WHERE source_attachment_id = ?",
            (attachment_id,),
        )
    return cur.rowcount


def _row_to_metric(row: sqlite3.Row) -> ExperimentMetric:
    return ExperimentMetric(
        id=row["id"],
        experiment_id=row["experiment_id"],
        name=row["name"],
        value=row["value"],
        created_at=row["created_at"],
        unit=row["unit"],
        split=row["split"],
        n=row["n"],
        stderr=row["stderr"],
        source_attachment_id=row["source_attachment_id"],
        recorded_by=row["recorded_by"],
        source=row["source"] or _derive_source(row["source_attachment_id"], row["recorded_by"]),
    )
