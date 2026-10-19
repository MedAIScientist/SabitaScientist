"""CRUD for cohort analysis: tables, immutable versions, the hash-chained trace,
analysis populations and analyses.

Two rules hold everywhere in this module and are the reason it exists at all:

* a version file is written once; a change of the rows creates a NEW version and
  one step of the chain (``record_step``) — nothing is ever edited in place;
* an analysis is bound to the population fingerprint it ran on, so a result can be
  recognised as stale instead of being shown as current.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..cohort.vendor.core.fingerprint import frame_fingerprint
from ..cohort.vendor.core.lineage import canonical_json, genesis_hash, seal_step
from ..db import get_db
from ..models import (
    CohortAnalysis,
    CohortAnalysisValue,
    CohortPopulation,
    CohortStep,
    CohortTable,
    CohortVersion,
)

__all__ = [
    "add_version",
    "create_table",
    "delete_table",
    "get_analysis",
    "get_population",
    "get_table",
    "get_version",
    "list_analyses",
    "list_analysis_values",
    "list_populations",
    "list_steps",
    "list_tables",
    "list_versions",
    "next_version_no",
    "record_step",
    "set_analysis_status",
    "store_analysis",
    "store_population",
    "update_table",
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------


def _row_to_table(row) -> CohortTable:
    return CohortTable(
        id=row["id"],
        project_id=row["project_id"],
        lab_id=row["lab_id"],
        data_origin=row["data_origin"],
        dataset_id=row["dataset_id"],
        name=row["name"],
        description=row["description"],
        config_json=row["config_json"],
        dictionary_json=row["dictionary_json"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_table(
    db_path: Path,
    *,
    project_id: str,
    name: str,
    created_by: str,
    lab_id: str | None = None,
    data_origin: str = "public",
    dataset_id: str | None = None,
    description: str | None = None,
    config: dict[str, Any] | None = None,
    dictionary: dict[str, Any] | None = None,
) -> CohortTable:
    table_id = _new_id()
    now = _now()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO cohort_tables
               (id, project_id, lab_id, data_origin, dataset_id, name, description,
                config_json, dictionary_json, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                table_id,
                project_id,
                lab_id,
                data_origin,
                dataset_id,
                name,
                description,
                _dump(config or {}),
                _dump(dictionary or {}),
                created_by,
                now,
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM cohort_tables WHERE id = ?", (table_id,)
        ).fetchone()
    return _row_to_table(row)


def get_table(db_path: Path, table_id: str) -> CohortTable | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM cohort_tables WHERE id = ?", (table_id,)
        ).fetchone()
    return _row_to_table(row) if row else None


def list_tables(db_path: Path, project_id: str) -> list[CohortTable]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cohort_tables WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        ).fetchall()
    return [_row_to_table(row) for row in rows]


def update_table(db_path: Path, table_id: str, **fields: Any) -> CohortTable | None:
    allowed = {
        "name",
        "description",
        "config_json",
        "dictionary_json",
        "data_origin",
        "dataset_id",
    }
    updates = {
        key: value
        for key, value in fields.items()
        if key in allowed and value is not None
    }
    if not updates:
        return get_table(db_path, table_id)
    updates["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with get_db(db_path) as conn:
        conn.execute(
            f"UPDATE cohort_tables SET {assignments} WHERE id = ?",
            (*updates.values(), table_id),
        )
    return get_table(db_path, table_id)


def delete_table(db_path: Path, table_id: str) -> None:
    with get_db(db_path) as conn:
        conn.execute("DELETE FROM cohort_tables WHERE id = ?", (table_id,))


# ---------------------------------------------------------------------------
# versions
# ---------------------------------------------------------------------------


def _row_to_version(row) -> CohortVersion:
    return CohortVersion(
        id=row["id"],
        table_id=row["table_id"],
        version_no=row["version_no"],
        rel_path=row["rel_path"],
        rows=row["rows"],
        columns=row["columns"],
        columns_json=row["columns_json"],
        content_sha256=row["content_sha256"],
        parent_version_id=row["parent_version_id"],
        parse_report_json=row["parse_report_json"],
        note=row["note"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def next_version_no(db_path: Path, table_id: str) -> int:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(version_no), 0) AS n FROM cohort_versions WHERE table_id = ?",
            (table_id,),
        ).fetchone()
    return int(row["n"]) + 1


def add_version(
    db_path: Path,
    *,
    table_id: str,
    version_no: int,
    rel_path: str,
    content_sha256: str,
    frame: pd.DataFrame,
    created_by: str,
    parent_version_id: str | None = None,
    parse_report: dict[str, Any] | None = None,
    note: str | None = None,
    columns: list[dict[str, Any]] | None = None,
) -> CohortVersion:
    version_id = _new_id()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO cohort_versions
               (id, table_id, version_no, rel_path, rows, columns, columns_json,
                content_sha256, parent_version_id, parse_report_json, note,
                created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                version_id,
                table_id,
                version_no,
                rel_path,
                len(frame),
                int(frame.shape[1]),
                _dump(columns or []),
                content_sha256,
                parent_version_id,
                _dump(parse_report) if parse_report else None,
                note,
                created_by,
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM cohort_versions WHERE id = ?", (version_id,)
        ).fetchone()
    return _row_to_version(row)


def get_version(db_path: Path, version_id: str) -> CohortVersion | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM cohort_versions WHERE id = ?", (version_id,)
        ).fetchone()
    return _row_to_version(row) if row else None


def list_versions(db_path: Path, table_id: str) -> list[CohortVersion]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cohort_versions WHERE table_id = ? ORDER BY version_no DESC",
            (table_id,),
        ).fetchall()
    return [_row_to_version(row) for row in rows]


def latest_version(db_path: Path, table_id: str) -> CohortVersion | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM cohort_versions WHERE table_id = ? ORDER BY version_no DESC LIMIT 1",
            (table_id,),
        ).fetchone()
    return _row_to_version(row) if row else None


# ---------------------------------------------------------------------------
# the hash-chained trace
# ---------------------------------------------------------------------------


def _row_to_step(row) -> CohortStep:
    return CohortStep(
        id=row["id"],
        table_id=row["table_id"],
        version_id=row["version_id"],
        seq=row["seq"],
        kind=row["kind"],
        params_json=row["params_json"],
        data_json=row["data_json"],
        out_version_id=row["out_version_id"],
        prev_hash=row["prev_hash"],
        hash=row["hash"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def list_steps(db_path: Path, table_id: str) -> list[CohortStep]:
    """Every step of a table's chain, oldest first."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cohort_steps WHERE table_id = ? ORDER BY seq", (table_id,)
        ).fetchall()
    return [_row_to_step(row) for row in rows]


def record_step(
    db_path: Path,
    *,
    table_id: str,
    version_id: str,
    kind: str,
    params: dict[str, Any],
    data: dict[str, Any],
    created_by: str | None,
    out_version_id: str | None = None,
) -> CohortStep:
    """Append one link to the table's chain.

    The hash covers the previous link, so editing, removing or reordering a step is
    detectable — which is the whole point of recording it.
    """
    with get_db(db_path) as conn:
        last = conn.execute(
            "SELECT seq, hash FROM cohort_steps WHERE table_id = ? ORDER BY seq DESC LIMIT 1",
            (table_id,),
        ).fetchone()
        seq = (int(last["seq"]) + 1) if last else 0
        prev_hash = str(last["hash"]) if last else genesis_hash(table_id)
        body = {
            "seq": seq,
            "table_id": table_id,
            "version_id": version_id,
            "kind": kind,
            "params": params,
            "data": data,
            "out_version_id": out_version_id,
            "created_by": created_by,
            "created_at": _now(),
        }
        sealed = seal_step(body, prev_hash)
        step_id = _new_id()
        conn.execute(
            """INSERT INTO cohort_steps
               (id, table_id, version_id, seq, kind, params_json, data_json,
                out_version_id, prev_hash, hash, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                step_id,
                table_id,
                version_id,
                seq,
                kind,
                # canonical_json (not _dump): the stored text must round-trip to the
                # exact values that were hashed, or verification would report tampering.
                canonical_json(params),
                canonical_json(data),
                out_version_id,
                prev_hash,
                sealed["hash"],
                created_by,
                body["created_at"],
            ),
        )
        row = conn.execute(
            "SELECT * FROM cohort_steps WHERE id = ?", (step_id,)
        ).fetchone()
    return _row_to_step(row)


def verify_chain(db_path: Path, table_id: str) -> dict[str, Any]:
    """Recompute every hash. Any edit, removal or reordering shows up here."""
    steps = list_steps(db_path, table_id)
    prev = genesis_hash(table_id)
    problems: list[str] = []
    for index, step in enumerate(steps):
        if step.seq != index:
            problems.append(
                f"step {index}: recorded as seq {step.seq} (a step is missing or reordered)"
            )
        if step.prev_hash != prev:
            problems.append(
                f"step {index} ({step.kind}): the chain does not link to the previous step"
            )
        body = {
            "seq": step.seq,
            "table_id": step.table_id,
            "version_id": step.version_id,
            "kind": step.kind,
            "params": json.loads(step.params_json),
            "data": json.loads(step.data_json),
            "out_version_id": step.out_version_id,
            "created_by": step.created_by,
            "created_at": step.created_at,
        }
        expected = seal_step(body, prev)["hash"]
        if expected != step.hash:
            problems.append(
                f"step {index} ({step.kind}): its content does not match its hash"
            )
        prev = step.hash
    return {
        "verified": not problems,
        "steps": len(steps),
        "problems": problems,
        "head": prev if steps else None,
    }


# ---------------------------------------------------------------------------
# populations
# ---------------------------------------------------------------------------


def _row_to_population(row) -> CohortPopulation:
    return CohortPopulation(
        id=row["id"],
        table_id=row["table_id"],
        version_id=row["version_id"],
        name=row["name"],
        criteria_json=row["criteria_json"],
        stages_json=row["stages_json"],
        counts_json=row["counts_json"],
        n_base=row["n_base"],
        n_included=row["n_included"],
        fingerprint=row["fingerprint"],
        superseded_by=row["superseded_by"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def store_population(
    db_path: Path,
    *,
    table_id: str,
    version_id: str,
    name: str,
    record: dict[str, Any],
    created_by: str,
) -> CohortPopulation:
    """Store a population and supersede the previous one for the same table.

    Superseding is what makes the older analyses stale: the study's population moved,
    so a result computed on the old rows is no longer the study's result.
    """
    population_id = _new_id()
    with get_db(db_path) as conn:
        # Insert first: the supersede UPDATE below points at this row, and foreign
        # keys are enforced, so it cannot name a population that does not exist yet.
        conn.execute(
            """INSERT INTO cohort_populations
               (id, table_id, version_id, name, criteria_json, stages_json, counts_json,
                n_base, n_included, fingerprint, superseded_by, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
            (
                population_id,
                table_id,
                version_id,
                name,
                _dump(record["criteria_json"]),
                _dump(record["stages_json"]),
                _dump(record["counts_json"]),
                record["n_base"],
                record["n_included"],
                record["fingerprint"],
                created_by,
                _now(),
            ),
        )
        conn.execute(
            "UPDATE cohort_populations SET superseded_by = ? "
            "WHERE table_id = ? AND superseded_by IS NULL AND id <> ?",
            (population_id, table_id, population_id),
        )
        row = conn.execute(
            "SELECT * FROM cohort_populations WHERE id = ?", (population_id,)
        ).fetchone()
    return _row_to_population(row)


def get_population(db_path: Path, population_id: str) -> CohortPopulation | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM cohort_populations WHERE id = ?", (population_id,)
        ).fetchone()
    return _row_to_population(row) if row else None


def list_populations(db_path: Path, table_id: str) -> list[CohortPopulation]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cohort_populations WHERE table_id = ? ORDER BY created_at DESC",
            (table_id,),
        ).fetchall()
    return [_row_to_population(row) for row in rows]


# ---------------------------------------------------------------------------
# analyses
# ---------------------------------------------------------------------------


def _row_to_analysis(row) -> CohortAnalysis:
    return CohortAnalysis(
        id=row["id"],
        population_id=row["population_id"],
        method=row["method"],
        params_json=row["params_json"],
        result_json=row["result_json"],
        table_json=row["table_json"],
        n=row["n"],
        engine_version=row["engine_version"],
        population_fingerprint=row["population_fingerprint"],
        status=row["status"],
        error=row["error"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def store_analysis(
    db_path: Path,
    *,
    population: CohortPopulation,
    method: str,
    params: dict[str, Any],
    result: dict[str, Any],
    table: dict[str, Any] | None,
    n: int,
    engine_version: str,
    values: list[dict[str, Any]],
    created_by: str,
    status: str = "current",
    error: str | None = None,
) -> CohortAnalysis:
    analysis_id = _new_id()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO cohort_analyses
               (id, population_id, method, params_json, result_json, table_json, n,
                engine_version, population_fingerprint, status, error, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                analysis_id,
                population.id,
                method,
                _dump(params),
                _dump(result),
                _dump(table) if table is not None else None,
                int(n),
                engine_version,
                population.fingerprint,
                status,
                error,
                created_by,
                _now(),
            ),
        )
        for value in values:
            if value.get("value") is None:
                continue
            conn.execute(
                """INSERT OR REPLACE INTO cohort_analysis_values
                   (analysis_id, name, label, value, unit, ci_low, ci_high, p_value, n)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    analysis_id,
                    value["name"],
                    value.get("label"),
                    float(value["value"]),
                    value.get("unit"),
                    value.get("ci_low"),
                    value.get("ci_high"),
                    value.get("p_value"),
                    value.get("n"),
                ),
            )
        row = conn.execute(
            "SELECT * FROM cohort_analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
    return _row_to_analysis(row)


def get_analysis(db_path: Path, analysis_id: str) -> CohortAnalysis | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM cohort_analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
    return _row_to_analysis(row) if row else None


def list_analyses(db_path: Path, population_id: str) -> list[CohortAnalysis]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cohort_analyses WHERE population_id = ? ORDER BY created_at DESC",
            (population_id,),
        ).fetchall()
    return [_row_to_analysis(row) for row in rows]


def list_analysis_values(db_path: Path, analysis_id: str) -> list[CohortAnalysisValue]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cohort_analysis_values WHERE analysis_id = ? ORDER BY name",
            (analysis_id,),
        ).fetchall()
    return [
        CohortAnalysisValue(
            analysis_id=row["analysis_id"],
            name=row["name"],
            value=row["value"],
            label=row["label"],
            unit=row["unit"],
            ci_low=row["ci_low"],
            ci_high=row["ci_high"],
            p_value=row["p_value"],
            n=row["n"],
        )
        for row in rows
    ]


def analysis_is_stale(
    analysis: CohortAnalysis, population: CohortPopulation | None
) -> bool:
    """A result is stale when the study's population moved, or the engine changed.

    Both are real: a superseded population means the analysed rows are no longer the
    study's rows, and a new engine version means the method itself changed.
    """
    if analysis.status == "failed":
        return False
    if population is None or population.superseded_by:
        return True
    from ..cohort.analyses import ENGINE_VERSION

    return analysis.engine_version != ENGINE_VERSION


def set_analysis_status(db_path: Path, analysis_id: str, status: str) -> None:
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE cohort_analyses SET status = ? WHERE id = ?", (status, analysis_id)
        )


def frame_hash(frame: pd.DataFrame) -> str:
    """The fingerprint a replay compares a recomputed frame against."""
    return frame_fingerprint(frame, index=True)


# ---------------------------------------------------------------------------
# the single write path
# ---------------------------------------------------------------------------


def write_version(
    db_path: Path,
    *,
    table: CohortTable,
    frame: pd.DataFrame,
    created_by: str,
    kind: str,
    params: dict[str, Any],
    data: dict[str, Any],
    columns: list[dict[str, Any]],
    parent_version_id: str | None = None,
    parse_report: dict[str, Any] | None = None,
    note: str | None = None,
) -> tuple[CohortVersion, CohortStep]:
    """Write a new immutable version and its step, in that order.

    This is the ONLY way rows enter or change: an import, a derived variable and a
    row subset all come through here, so the chain has no gaps and replay has one
    shape to handle.
    """
    from ..cohort import store

    version_no = next_version_no(db_path, table.id)
    rel_path, content_sha256 = store.write_version(table.id, version_no, frame)
    version = add_version(
        db_path,
        table_id=table.id,
        version_no=version_no,
        rel_path=rel_path,
        content_sha256=content_sha256,
        frame=frame,
        created_by=created_by,
        parent_version_id=parent_version_id,
        parse_report=parse_report,
        note=note,
        columns=columns,
    )
    step = record_step(
        db_path,
        table_id=table.id,
        version_id=parent_version_id or version.id,
        kind=kind,
        params=params,
        data=data,
        created_by=created_by,
        out_version_id=version.id,
    )
    return version, step


def purge_versions_files(table_id: str) -> None:
    """Remove a table's version files after its rows are gone."""
    from ..cohort import store

    store.purge_table(table_id)
