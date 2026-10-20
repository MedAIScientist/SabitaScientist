"""Cohort analysis: /api/v1/projects/{project_id}/cohort/*.

Phases 1-4 of ``plan/cohort-analiz-roadmap.md``:

1. an immutable, versioned table with a declared analysis population and its
   STROBE participant flow;
2. a data-quality scorecard, a hash-chained trace, and a replay that says whether
   the recorded steps still reproduce the analysed table;
3. Table 1, description and group comparison from the vendored statistics engine;
4. every result carries the population fingerprint it was computed on, is marked
   stale when that population moves, and can publish its numbers into
   ``experiment_metrics``, where ``verify_numbers`` will find them.

The statistics run in the request thread: FastAPI runs a ``def`` handler in its
threadpool, so the event loop is not blocked, and the importer enforces a row
ceiling. ``gazzali/cohort`` imports no FastAPI and no SQLite, so the engine can move
to a worker process later without being rewritten.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from ...cohort import dossier, engine, ingest, quality, transform
from ...cohort.analyses import ENGINE_VERSION
from ...crud import cohort as crud
from ...crud.audit import log_action as audit_log
from ...crud.datasets import get_dataset, list_grants, list_irb_ids
from ...crud.experiment_metrics import create_metrics
from ...crud.experiments import get_experiment
from ...crud.irb import get_irb
from ...crud.projects import get_project
from ...db import get_db, get_db_path
from ...metrics_csv import ParsedMetric
from ...models import CohortTable, User
from ...settings import get_max_upload_bytes
from ..deps import require_project_role
from ..schemas import (
    CohortAnalysisCreate,
    CohortAnalysisResponse,
    CohortAnalysisValueResponse,
    CohortCriterion,
    CohortPopulationCreate,
    CohortPopulationResponse,
    CohortPublishRequest,
    CohortPublishResponse,
    CohortReplayResponse,
    CohortReplayStep,
    CohortStepResponse,
    CohortTableCreate,
    CohortTableResponse,
    CohortTableUpdate,
    CohortTraceResponse,
    CohortVersionResponse,
)

router = APIRouter()

_MAX_BYTES = get_max_upload_bytes()
_PREVIEW_ROWS = 50
# A dataset may be analysed once it is approved; 'sealed' data is read-only but
# still analysable, which is exactly what a finished cohort is.
_ANALYSABLE_DATASET_STATUSES = {"approved", "delivering", "sealed"}
_APPROVED_IRB_STATUS = "approved"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _unprocessable(detail: str) -> HTTPException:
    # The literal 422 matches the rest of the codebase: the starlette constant for it
    # is deprecated in favour of a name this version does not export.
    return HTTPException(status_code=422, detail=detail)


def _load_table(project_id: str, table_id: str) -> CohortTable:
    table = crud.get_table(get_db_path(), table_id)
    if not table or table.project_id != project_id:
        raise _not_found("Cohort table not found")
    return table


def _load_version(table: CohortTable, version_id: str):
    version = crud.get_version(get_db_path(), version_id)
    if not version or version.table_id != table.id:
        raise _not_found("Version not found")
    return version


def _load_population(table: CohortTable, population_id: str):
    population = crud.get_population(get_db_path(), population_id)
    if not population or population.table_id != table.id:
        raise _not_found("Analysis population not found")
    return population


def _load_analysis(table: CohortTable, analysis_id: str):
    analysis = crud.get_analysis(get_db_path(), analysis_id)
    if not analysis:
        raise _not_found("Analysis not found")
    population = crud.get_population(get_db_path(), analysis.population_id)
    if not population or population.table_id != table.id:
        raise _not_found("Analysis not found")
    return analysis, population


def _criteria_ids(population) -> list[str]:
    return [str(item["id"]) for item in json.loads(population.criteria_json or "[]")]


def _config(table: CohortTable) -> dict[str, Any]:
    return json.loads(table.config_json or "{}")


def _dictionary(table: CohortTable) -> dict[str, Any]:
    return json.loads(table.dictionary_json or "{}")


def _version_response(version) -> CohortVersionResponse:
    return CohortVersionResponse(
        id=version.id,
        table_id=version.table_id,
        version_no=version.version_no,
        rows=version.rows,
        columns=version.columns,
        columns_meta=json.loads(version.columns_json or "[]"),
        content_sha256=version.content_sha256,
        parent_version_id=version.parent_version_id,
        parse_report=json.loads(version.parse_report_json)
        if version.parse_report_json
        else None,
        note=version.note,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def _population_response(population) -> CohortPopulationResponse:
    return CohortPopulationResponse(
        id=population.id,
        table_id=population.table_id,
        version_id=population.version_id,
        name=population.name,
        criteria=json.loads(population.criteria_json or "[]"),
        stages=json.loads(population.stages_json or "[]"),
        counts=json.loads(population.counts_json or "[]"),
        n_base=population.n_base,
        n_included=population.n_included,
        fingerprint=population.fingerprint,
        superseded_by=population.superseded_by,
        created_by=population.created_by,
        created_at=population.created_at,
    )


def _table_response(table: CohortTable) -> CohortTableResponse:
    db = get_db_path()
    versions = crud.list_versions(db, table.id)
    populations = crud.list_populations(db, table.id)
    active = next((p for p in populations if not p.superseded_by), None)
    return CohortTableResponse(
        id=table.id,
        project_id=table.project_id,
        lab_id=table.lab_id,
        name=table.name,
        description=table.description,
        data_origin=table.data_origin,
        dataset_id=table.dataset_id,
        config=_config(table),
        dictionary=_dictionary(table),
        created_by=table.created_by,
        created_at=table.created_at,
        updated_at=table.updated_at,
        versions=[_version_response(v) for v in versions],
        latest_version=_version_response(versions[0]) if versions else None,
        populations=[_population_response(p) for p in populations],
        active_population=_population_response(active) if active else None,
    )


def _check_governance(dataset_id: str | None, project_id: str) -> None:
    """A 'governed' cohort needs an approved dataset, a live grant and an unexpired IRB.

    Public and synthetic cohorts skip this entirely; the gate exists so that real
    patient data cannot be analysed by naming a dataset id and nothing else.
    """
    if not dataset_id:
        raise _conflict("a governed cohort must name the dataset its rows came from")
    db = get_db_path()
    dataset = get_dataset(db, dataset_id)
    if not dataset:
        raise _not_found("Dataset not found")
    if dataset.status not in _ANALYSABLE_DATASET_STATUSES:
        raise _conflict(
            f"dataset '{dataset.name}' is '{dataset.status}'; "
            "only an approved dataset can be analysed"
        )
    granted = [
        grant
        for grant in list_grants(db, dataset_id)
        if grant.project_id == project_id
        and grant.admin_approved_at is not None
        and grant.revoked_at is None
        and (not grant.expires_at or grant.expires_at >= _today())
    ]
    if not granted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this project holds no active grant on the dataset",
        )
    irb_ids = list_irb_ids(db, dataset_id)
    if not irb_ids:
        raise _conflict("the dataset has no linked ethics approval")
    live = [
        irb
        for irb in (get_irb(db, irb_id) for irb_id in irb_ids)
        if irb
        and irb.status == _APPROVED_IRB_STATUS
        and (not irb.expiry_date or irb.expiry_date >= _today())
    ]
    if not live:
        raise _conflict(
            "no linked ethics approval is currently approved and unexpired; "
            "renew the IRB before analysing patient data"
        )


def _analysis_response(analysis, population) -> CohortAnalysisResponse:
    stale = crud.analysis_is_stale(analysis, population)
    reason = None
    if stale:
        reason = (
            "the study's analysis population was superseded after this result was computed"
            if population is None or population.superseded_by
            else f"computed by engine {analysis.engine_version}, now {ENGINE_VERSION}"
        )
    return CohortAnalysisResponse(
        id=analysis.id,
        population_id=analysis.population_id,
        method=analysis.method,
        params=json.loads(analysis.params_json or "{}"),
        result=json.loads(analysis.result_json or "{}"),
        table=json.loads(analysis.table_json) if analysis.table_json else None,
        n=analysis.n,
        engine_version=analysis.engine_version,
        population_fingerprint=analysis.population_fingerprint,
        status="stale" if stale else analysis.status,
        stale_reason=reason,
        error=analysis.error,
        created_by=analysis.created_by,
        created_at=analysis.created_at,
        values=[
            CohortAnalysisValueResponse(
                name=value.name,
                label=value.label,
                value=value.value,
                unit=value.unit,
                ci_low=value.ci_low,
                ci_high=value.ci_high,
                p_value=value.p_value,
                n=value.n,
            )
            for value in crud.list_analysis_values(get_db_path(), analysis.id)
        ],
    )


def _refuse_if_stale(analysis, population) -> None:
    """Refuse to publish a number the app already knows is out of date."""
    if analysis.status == "failed":
        raise _conflict("a failed analysis has no numbers to publish")
    if crud.analysis_is_stale(analysis, population):
        raise _conflict(
            "this result is stale: recompute it on the current analysis population "
            "before publishing its numbers"
        )


def _population_rows(table: CohortTable, population, version):
    """Load the version and restrict it to the declared population."""
    frame = engine.load_frame(version)
    result = engine.evaluate(frame, _config(table), _criteria_ids(population))
    return engine.population_frame(frame, result), result


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/cohort/tables",
    response_model=CohortTableResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cohort_table(
    project_id: str,
    payload: CohortTableCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    if payload.data_origin == "governed":
        _check_governance(payload.dataset_id, project_id)
    elif payload.dataset_id:
        raise _conflict(
            "a public or synthetic cohort cannot be linked to a governed dataset"
        )
    db = get_db_path()
    project = get_project(db, project_id)
    if not project:
        raise _not_found("Project not found")
    if any(t.name == payload.name for t in crud.list_tables(db, project_id)):
        raise _conflict(
            f"this project already has a cohort table named '{payload.name}'"
        )
    table = crud.create_table(
        db,
        project_id=project_id,
        name=payload.name,
        created_by=current_user.id,
        lab_id=project.lab_id,
        data_origin=payload.data_origin,
        dataset_id=payload.dataset_id,
        description=payload.description,
        dictionary=payload.dictionary,
    )
    audit_log(
        db,
        current_user.id,
        "cohort_table_create",
        "cohort_table",
        table.id,
        f"{payload.name} ({payload.data_origin})",
    )
    return _table_response(table)


@router.get("/{project_id}/cohort/tables", response_model=list[CohortTableResponse])
def list_cohort_tables(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    return [
        _table_response(table) for table in crud.list_tables(get_db_path(), project_id)
    ]


@router.get(
    "/{project_id}/cohort/tables/{table_id}", response_model=CohortTableResponse
)
def get_cohort_table(
    project_id: str,
    table_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    return _table_response(_load_table(project_id, table_id))


@router.get(
    "/{project_id}/cohort/tables/{table_id}/criteria",
    response_model=list[CohortCriterion],
)
def list_cohort_criteria(
    project_id: str,
    table_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """The criteria of the study configuration, for the population tick list."""
    table = _load_table(project_id, table_id)
    return engine.catalogue_payload(_config(table))


@router.patch(
    "/{project_id}/cohort/tables/{table_id}", response_model=CohortTableResponse
)
def update_cohort_table(
    project_id: str,
    table_id: str,
    payload: CohortTableUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    table = _load_table(project_id, table_id)
    fields: dict[str, Any] = {}
    if payload.name is not None:
        fields["name"] = payload.name
    if payload.description is not None:
        fields["description"] = payload.description
    if payload.config is not None:
        fields["config_json"] = json.dumps(payload.config, sort_keys=True)
    if payload.dictionary is not None:
        fields["dictionary_json"] = json.dumps(payload.dictionary, sort_keys=True)
    if fields.get("config_json") is not None:
        # A configuration with a criterion nobody can evaluate would fail later, at
        # analysis time; validating the shape here keeps the failure next to the edit.
        try:
            engine.catalogue_payload(payload.config or {})
        except Exception as exc:
            raise _unprocessable(f"invalid study configuration: {exc}") from exc
    updated = crud.update_table(get_db_path(), table.id, **fields)
    audit_log(
        get_db_path(),
        current_user.id,
        "cohort_table_update",
        "cohort_table",
        table.id,
        ", ".join(sorted(fields)),
    )
    return _table_response(updated or table)


@router.delete(
    "/{project_id}/cohort/tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_cohort_table(
    project_id: str,
    table_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    table = _load_table(project_id, table_id)
    db = get_db_path()
    crud.delete_table(db, table.id)
    crud.purge_versions_files(table.id)
    audit_log(
        db, current_user.id, "cohort_table_delete", "cohort_table", table.id, table.name
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# versions
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/cohort/tables/{table_id}/versions",
    response_model=CohortVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_cohort_version(
    project_id: str,
    table_id: str,
    file: UploadFile,
    note: str | None = Query(default=None, max_length=500),
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Read an uploaded file into a new immutable version and record the import."""
    table = _load_table(project_id, table_id)
    content = await file.read()
    if len(content) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {_MAX_BYTES // (1024 * 1024)} MB upload limit.",
        )
    try:
        frame, report = ingest.read_upload(file.filename or "upload.csv", content)
    except ingest.IngestError as exc:
        raise _unprocessable(str(exc)) from exc

    db = get_db_path()
    version, _ = crud.write_version(
        db,
        table=table,
        frame=frame,
        created_by=current_user.id,
        kind="import",
        params={
            "filename": report.filename,
            "encoding": report.encoding,
            "delimiter": report.delimiter,
        },
        data={
            "rows_in": len(frame) + int(report.skipped_lines) + int(report.blanks),
            "rows_out": len(frame),
            "rows_removed": int(report.skipped_lines) + int(report.blanks),
            "rows_added": 0,
            "columns_out": int(frame.shape[1]),
        },
        columns=ingest.columns_payload(frame),
        parse_report=report.to_dict(),
        note=note,
    )
    # Every table starts with a population that excludes nothing, so an analysis
    # always has a declared population behind it.
    crud.store_population(
        db,
        table_id=table.id,
        version_id=version.id,
        name="All rows (no criteria)",
        record=engine.population_record(engine.evaluate(frame, None, [])),
        created_by=current_user.id,
    )
    audit_log(
        db,
        current_user.id,
        "cohort_version_upload",
        "cohort_table",
        table.id,
        f"v{version.version_no}: {len(frame)} rows from {report.filename}",
    )
    return _version_response(version)


@router.get(
    "/{project_id}/cohort/tables/{table_id}/versions",
    response_model=list[CohortVersionResponse],
)
def list_cohort_versions(
    project_id: str,
    table_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    table = _load_table(project_id, table_id)
    return [_version_response(v) for v in crud.list_versions(get_db_path(), table.id)]


@router.get(
    "/{project_id}/cohort/tables/{table_id}/versions/{version_id}",
    response_model=CohortVersionResponse,
)
def get_cohort_version(
    project_id: str,
    table_id: str,
    version_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    table = _load_table(project_id, table_id)
    return _version_response(_load_version(table, version_id))


@router.get("/{project_id}/cohort/tables/{table_id}/versions/{version_id}/preview")
def preview_cohort_version(
    project_id: str,
    table_id: str,
    version_id: str,
    limit: int = Query(default=_PREVIEW_ROWS, ge=1, le=200),
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    table = _load_table(project_id, table_id)
    version = _load_version(table, version_id)
    try:
        frame = engine.load_frame(version)
    except engine.EngineError as exc:
        raise _conflict(str(exc)) from exc
    head = frame.head(limit)
    return {
        "version_id": version.id,
        "rows": len(frame),
        "shown": len(head),
        "columns": [str(c) for c in frame.columns],
        "rows_data": json.loads(
            head.reset_index().to_json(orient="records", date_format="iso")
        ),
    }


@router.post(
    "/{project_id}/cohort/tables/{table_id}/versions/{version_id}/derive",
    response_model=CohortVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def derive_cohort_variable(
    project_id: str,
    table_id: str,
    version_id: str,
    payload: dict,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Add a column computed by the sandboxed expression language; writes a new version."""
    table = _load_table(project_id, table_id)
    version = _load_version(table, version_id)
    name = str(payload.get("name") or "").strip()
    expression = str(payload.get("expression") or "")
    try:
        frame = engine.load_frame(version)
        derived = transform.derive(
            frame, name, expression, overwrite=bool(payload.get("overwrite", False))
        )
    except (engine.EngineError, transform.TransformError) as exc:
        raise _unprocessable(str(exc)) from exc
    new_version, _ = crud.write_version(
        get_db_path(),
        table=table,
        frame=derived,
        created_by=current_user.id,
        kind="derive",
        params={"name": name, "expression": expression},
        data=transform.summarize_change(frame, derived),
        columns=ingest.columns_payload(derived),
        parent_version_id=version.id,
        note=f"derived {name}",
    )
    return _version_response(new_version)


@router.post(
    "/{project_id}/cohort/tables/{table_id}/versions/{version_id}/filter",
    response_model=CohortVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def filter_cohort_rows(
    project_id: str,
    table_id: str,
    version_id: str,
    payload: dict,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Keep or drop explicit rows (inclusive id ranges); writes a new version."""
    table = _load_table(project_id, table_id)
    version = _load_version(table, version_id)
    action = str(payload.get("action") or "drop")
    row_ids = payload.get("row_ids") or []
    if not isinstance(row_ids, list):
        raise _unprocessable("row_ids must be a list of [first, last] ranges")
    try:
        frame = engine.load_frame(version)
        filtered, removed = transform.filter_rows(frame, action=action, row_ids=row_ids)
    except (engine.EngineError, transform.TransformError) as exc:
        raise _unprocessable(str(exc)) from exc
    new_version, _ = crud.write_version(
        get_db_path(),
        table=table,
        frame=filtered,
        created_by=current_user.id,
        kind="filter",
        params={"action": action, "row_ids": row_ids},
        data=transform.summarize_change(frame, filtered),
        columns=ingest.columns_payload(filtered),
        parent_version_id=version.id,
        note=f"{action} {removed} row(s)",
    )
    return _version_response(new_version)


@router.get("/{project_id}/cohort/tables/{table_id}/versions/{version_id}/quality")
def cohort_version_quality(
    project_id: str,
    table_id: str,
    version_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    table = _load_table(project_id, table_id)
    version = _load_version(table, version_id)
    try:
        frame = engine.load_frame(version)
    except engine.EngineError as exc:
        raise _conflict(str(exc)) from exc
    report = quality.audit(frame, _config(table))
    return {
        "version_id": version.id,
        "version_no": version.version_no,
        **report.to_dict(),
    }


# ---------------------------------------------------------------------------
# trace and replay
# ---------------------------------------------------------------------------


def _step_response(step) -> CohortStepResponse:
    return CohortStepResponse(
        id=step.id,
        seq=step.seq,
        kind=step.kind,
        params=json.loads(step.params_json or "{}"),
        data=json.loads(step.data_json or "{}"),
        version_id=step.version_id,
        out_version_id=step.out_version_id,
        prev_hash=step.prev_hash,
        hash=step.hash,
        created_by=step.created_by,
        created_at=step.created_at,
    )


@router.get(
    "/{project_id}/cohort/tables/{table_id}/trace", response_model=CohortTraceResponse
)
def cohort_trace(
    project_id: str,
    table_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    table = _load_table(project_id, table_id)
    db = get_db_path()
    return CohortTraceResponse(
        table_id=table.id,
        steps=[_step_response(step) for step in crud.list_steps(db, table.id)],
        chain=crud.verify_chain(db, table.id),
    )


@router.post(
    "/{project_id}/cohort/tables/{table_id}/replay", response_model=CohortReplayResponse
)
def replay_cohort_trace(
    project_id: str,
    table_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Recompute every step and compare it with what was recorded.

    A replay that reproduces the analysed table is the strongest claim this module
    makes. When it does not, the step and the reason are named instead of a
    reassuring 'OK'.
    """
    table = _load_table(project_id, table_id)
    db = get_db_path()
    problems: list[str] = []
    results: list[CohortReplayStep] = []

    def note(
        step, kind: str, version_no: int | None, outcome: str, detail: str
    ) -> None:
        results.append(
            CohortReplayStep(
                seq=step.seq,
                kind=kind,
                version_no=version_no,
                status=outcome,
                detail=detail,
            )
        )

    for step in crud.list_steps(db, table.id):
        params = json.loads(step.params_json or "{}")
        try:
            if step.kind == "import":
                version = crud.get_version(db, step.out_version_id or step.version_id)
                if version is None:
                    note(
                        step,
                        step.kind,
                        None,
                        "missing",
                        "the imported version no longer exists",
                    )
                    problems.append(f"step {step.seq}: imported version is missing")
                    continue
                engine.load_frame(version)  # re-checks the recorded content hash
                note(
                    step,
                    step.kind,
                    version.version_no,
                    "verified",
                    "the file still matches its recorded hash",
                )
                continue

            if step.kind in ("derive", "filter"):
                parent = crud.get_version(db, step.version_id)
                child = crud.get_version(db, step.out_version_id or "")
                if parent is None or child is None:
                    note(
                        step,
                        step.kind,
                        None,
                        "missing",
                        "a version this step needs no longer exists",
                    )
                    problems.append(f"step {step.seq}: version missing")
                    continue
                source = engine.load_frame(parent)
                if step.kind == "derive":
                    recomputed = transform.derive(
                        source,
                        str(params.get("name") or ""),
                        str(params.get("expression") or ""),
                        overwrite=True,
                    )
                else:
                    recomputed, _ = transform.filter_rows(
                        source,
                        action=str(params.get("action") or "drop"),
                        row_ids=params.get("row_ids") or [],
                    )
                recorded = engine.load_frame(child)
                if crud.frame_hash(recomputed) == crud.frame_hash(recorded):
                    note(
                        step,
                        step.kind,
                        child.version_no,
                        "verified",
                        "recomputing the step reproduces the recorded table",
                    )
                else:
                    detail = _describe_frame_difference(recomputed, recorded)
                    note(step, step.kind, child.version_no, "differs", detail)
                    problems.append(f"step {step.seq} ({step.kind}): {detail}")
                continue

            if step.kind == "population":
                version = crud.get_version(db, step.version_id)
                if version is None:
                    note(
                        step,
                        step.kind,
                        None,
                        "missing",
                        "the version this population was computed on is missing",
                    )
                    problems.append(f"step {step.seq}: version missing")
                    continue
                frame = engine.load_frame(version)
                result = engine.evaluate(
                    frame, _config(table), list(params.get("criteria") or [])
                )
                expected = str(
                    (json.loads(step.data_json or "{}") or {}).get("fingerprint") or ""
                )
                if result.fingerprint == expected:
                    note(
                        step,
                        step.kind,
                        version.version_no,
                        "verified",
                        f"the criteria still select the same {result.n_included} row(s)",
                    )
                else:
                    note(
                        step,
                        step.kind,
                        version.version_no,
                        "differs",
                        "the recorded criteria no longer select the same rows",
                    )
                    problems.append(
                        f"step {step.seq} (population): fingerprints differ"
                    )
                continue

            note(
                step,
                step.kind,
                None,
                "not_replayable",
                "this step kind cannot be recomputed",
            )
        except Exception as exc:
            note(step, step.kind, None, "failed", str(exc))
            problems.append(f"step {step.seq} ({step.kind}): {exc}")

    return CohortReplayResponse(
        table_id=table.id, steps=results, reconciled=not problems, problems=problems
    )


def _describe_frame_difference(recomputed, recorded) -> str:
    """Say where two frames differ, so the report is actionable rather than 'differs'."""
    if recomputed.shape != recorded.shape:
        return (
            f"the recomputed table has shape {recomputed.shape}, "
            f"the recorded one {recorded.shape}"
        )
    if list(recomputed.columns) != list(recorded.columns):
        return "the recomputed table has different columns"
    for column in recorded.columns:
        left, right = recomputed[column], recorded[column]
        try:
            differ = ~((left == right) | (left.isna() & right.isna()))
        except (TypeError, ValueError):
            differ = left.astype(str) != right.astype(str)
        count = int(differ.sum())
        if count:
            return f"{count} value(s) differ in column '{column}'"
    return (
        "the values are equal but the table fingerprint differs (index or dtype change)"
    )


# ---------------------------------------------------------------------------
# populations
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/cohort/tables/{table_id}/populations",
    response_model=CohortPopulationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cohort_population(
    project_id: str,
    table_id: str,
    payload: CohortPopulationCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Evaluate the ticked criteria and declare the analysis population.

    Creating a population supersedes the previous one, which is what makes the older
    analyses stale instead of silently current.
    """
    table = _load_table(project_id, table_id)
    db = get_db_path()
    version = (
        _load_version(table, payload.version_id)
        if payload.version_id
        else crud.latest_version(db, table.id)
    )
    if version is None:
        raise _conflict("this table has no data yet; upload a version first")
    try:
        frame = engine.load_frame(version)
        result = engine.evaluate(frame, _config(table), payload.criteria)
        record = engine.population_record(result)
    except engine.EngineError as exc:
        raise _unprocessable(str(exc)) from exc
    population = crud.store_population(
        db,
        table_id=table.id,
        version_id=version.id,
        name=payload.name,
        record=record,
        created_by=current_user.id,
    )
    crud.record_step(
        db,
        table_id=table.id,
        version_id=version.id,
        kind="population",
        params={"name": payload.name, "criteria": payload.criteria},
        data={
            "rows_in": result.n_base,
            "rows_out": result.n_included,
            "rows_removed": result.n_base - result.n_included,
            "fingerprint": result.fingerprint,
            "n_included": result.n_included,
        },
        created_by=current_user.id,
    )
    return _population_response(population)


@router.get(
    "/{project_id}/cohort/tables/{table_id}/populations",
    response_model=list[CohortPopulationResponse],
)
def list_cohort_populations(
    project_id: str,
    table_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    table = _load_table(project_id, table_id)
    return [
        _population_response(p) for p in crud.list_populations(get_db_path(), table.id)
    ]


def _build_flow(table: CohortTable, population) -> dict:
    """The participant flow of a population, from the trace the table recorded.

    Shared by the flow endpoint and the dossier so the document cannot disagree with the
    screen about how many rows were excluded.
    """
    db = get_db_path()
    version = crud.get_version(db, population.version_id)
    if version is None:
        raise _not_found("Version not found")
    try:
        frame = engine.load_frame(version)
        result = engine.evaluate(frame, _config(table), _criteria_ids(population))
    except engine.EngineError as exc:
        raise _conflict(str(exc)) from exc

    analyses = [
        {
            "label": f"{analysis.method} (n = {analysis.n:,})",
            "n_population": population.n_included,
            "n_analysed": analysis.n,
        }
        for analysis in crud.list_analyses(db, population.id)
        if not crud.analysis_is_stale(analysis, population)
    ]
    report = json.loads(version.parse_report_json) if version.parse_report_json else {}
    source = None
    n_loaded = version.rows
    if report.get("lines"):
        # lines counts non-empty lines of the file, header included.
        n_read = int(report["lines"]) - 1
        skipped = int(report.get("skipped_lines") or 0) + int(report.get("blanks") or 0)
        source = {
            "name": report.get("filename") or table.name,
            "n_read": n_read,
            "n_skipped": skipped,
        }
        n_loaded = None  # the flow derives it as n_read - n_skipped
    steps = [
        {
            "data": json.loads(step.data_json or "{}"),
            "function": step.kind,
            "description": step.kind.replace("_", " "),
        }
        for step in crud.list_steps(db, table.id)
        if step.kind in ("derive", "filter")
    ]
    return engine.build_flow(
        result,
        dataset=table.name,
        n_loaded=n_loaded,
        source=source,
        steps=steps,
        analyses_=analyses,
    )


@router.get("/{project_id}/cohort/tables/{table_id}/populations/{population_id}/flow")
def cohort_participant_flow(
    project_id: str,
    table_id: str,
    population_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """The STROBE participant flow (item 13), with its own consistency check."""
    table = _load_table(project_id, table_id)
    population = _load_population(table, population_id)
    return _build_flow(table, population)


# ---------------------------------------------------------------------------
# analyses
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/cohort/tables/{table_id}/populations/{population_id}/analyses",
    response_model=CohortAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cohort_analysis(
    project_id: str,
    table_id: str,
    population_id: str,
    payload: CohortAnalysisCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    table = _load_table(project_id, table_id)
    population = _load_population(table, population_id)
    db = get_db_path()
    version = crud.get_version(db, population.version_id)
    if version is None:
        raise _not_found("Version not found")
    params = payload.model_dump(exclude_none=True)
    try:
        rows, _ = _population_rows(table, population, version)
        outcome = engine.run(
            rows, payload.method, params, dictionary=_dictionary(table)
        )
    except engine.EngineError as exc:
        raise _unprocessable(str(exc)) from exc
    analysis = crud.store_analysis(
        db,
        population=population,
        method=outcome.method,
        params=params,
        result=outcome.result,
        table=outcome.table,
        n=outcome.n,
        engine_version=ENGINE_VERSION,
        values=outcome.values,
        created_by=current_user.id,
    )
    return _analysis_response(analysis, population)


@router.get(
    "/{project_id}/cohort/tables/{table_id}/populations/{population_id}/analyses",
    response_model=list[CohortAnalysisResponse],
)
def list_cohort_analyses(
    project_id: str,
    table_id: str,
    population_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    table = _load_table(project_id, table_id)
    population = _load_population(table, population_id)
    return [
        _analysis_response(analysis, population)
        for analysis in crud.list_analyses(get_db_path(), population.id)
    ]


@router.get(
    "/{project_id}/cohort/tables/{table_id}/analyses/{analysis_id}",
    response_model=CohortAnalysisResponse,
)
def get_cohort_analysis(
    project_id: str,
    table_id: str,
    analysis_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    table = _load_table(project_id, table_id)
    analysis, population = _load_analysis(table, analysis_id)
    return _analysis_response(analysis, population)


@router.get("/{project_id}/cohort/tables/{table_id}/analyses/{analysis_id}/export")
def export_cohort_analysis(
    project_id: str,
    table_id: str,
    analysis_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """The rendered table as CSV, with the fingerprint of the population it came from."""
    table = _load_table(project_id, table_id)
    analysis, population = _load_analysis(table, analysis_id)
    rendered = json.loads(analysis.table_json) if analysis.table_json else None
    if not rendered:
        raise _conflict("this analysis has no table to export")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([f"# table: {table.name}"])
    writer.writerow([f"# population: {population.name} (n = {population.n_included})"])
    writer.writerow([f"# fingerprint: {analysis.population_fingerprint}"])
    writer.writerow([f"# method: {analysis.method}; n analysed = {analysis.n}"])
    writer.writerow([f"# engine: {analysis.engine_version}"])
    writer.writerow([])

    columns = rendered.get("columns") or []
    if columns and isinstance(columns[0], dict):
        # Rendered shape: the row label is its own leading column, then one field per
        # column. The header must carry that leading column too, or every row would be
        # one field longer than the header.
        writer.writerow(["Variable"] + [column["label"] for column in columns])
        for row in rendered.get("rows") or []:
            cells = row.get("cells")
            if cells is not None:
                writer.writerow(
                    [row.get("label")]
                    + [cells.get(column["key"], "") for column in columns]
                )
            else:
                writer.writerow(
                    [
                        row.get("label"),
                        row.get("n", ""),
                        row.get("missing", ""),
                        row.get("mean_sd", ""),
                        row.get("median_iqr", ""),
                    ]
                )
    else:
        writer.writerow(columns)
        for row in rendered.get("rows") or []:
            writer.writerow([row.get("label"), row.get("value"), row.get("missing")])
    for note in rendered.get("notes") or []:
        writer.writerow([f"# {note}"])

    filename = f"cohort-{table.name}-{analysis.method}-{analysis.id[:8]}.csv".replace(
        " ", "_"
    )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{project_id}/cohort/tables/{table_id}/analyses/{analysis_id}/publish",
    response_model=CohortPublishResponse,
)
def publish_cohort_analysis(
    project_id: str,
    table_id: str,
    analysis_id: str,
    payload: CohortPublishRequest,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Copy the selected numbers into ``experiment_metrics``.

    From there they are the numbers the paper drafter may cite: ``verify_numbers``
    accepts a draft number only if it matches a recorded metric. A stale analysis is
    refused here rather than published as if it were current.
    """
    table = _load_table(project_id, table_id)
    analysis, population = _load_analysis(table, analysis_id)
    _refuse_if_stale(analysis, population)
    db = get_db_path()
    experiment = get_experiment(db, payload.experiment_id)
    if not experiment or experiment.project_id != project_id:
        raise _not_found("Experiment not found in this project")

    values = crud.list_analysis_values(db, analysis.id)
    if payload.names:
        wanted = set(payload.names)
        values = [value for value in values if value.name in wanted]
        unknown = sorted(wanted - {value.name for value in values})
        if unknown:
            raise _unprocessable("unknown values: " + ", ".join(unknown))
    if not values:
        raise _conflict("this analysis produced no publishable numbers")

    metrics = create_metrics(
        db,
        experiment.id,
        [
            ParsedMetric(
                name=value.name,
                value=float(value.value),
                unit=value.unit,
                n=value.n,
            )
            for value in values
        ],
        recorded_by=current_user.id,
        source=f"cohort:{analysis.id}",
    )
    with get_db(db) as conn:
        for metric in metrics:
            conn.execute(
                "UPDATE experiment_metrics SET source_analysis_id = ? WHERE id = ?",
                (analysis.id, metric.id),
            )
    audit_log(
        db,
        current_user.id,
        "cohort_publish",
        "cohort_analysis",
        analysis.id,
        f"{len(metrics)} value(s) to experiment {experiment.id}",
    )
    return CohortPublishResponse(
        analysis_id=analysis.id,
        experiment_id=experiment.id,
        published=[
            {
                "name": value.name,
                "label": value.label,
                "value": value.value,
                "n": value.n,
            }
            for value in values
        ],
    )


@router.get("/{project_id}/cohort/tables/{table_id}/dossier")
def cohort_dossier(
    project_id: str,
    table_id: str,
    analysis_id: list[str] = Query(default=[]),
    population_id: str | None = Query(default=None),
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """The study dossier: provenance, participant flow, data handling, missingness, results.

    By default it carries every CURRENT analysis of the study's population. Results
    computed on a superseded population are left out — unless one is named explicitly,
    in which case it is included and marked stale in the document.
    """
    table = _load_table(project_id, table_id)
    db = get_db_path()
    populations = crud.list_populations(db, table.id)
    if population_id:
        population = _load_population(table, population_id)
    else:
        population = next(
            (item for item in populations if not item.superseded_by), None
        )
    if population is None:
        raise _conflict("this table has no analysis population yet")

    version = crud.get_version(db, population.version_id)
    if version is None:
        raise _not_found("Version not found")
    try:
        frame = engine.load_frame(version)
    except engine.EngineError as exc:
        raise _conflict(str(exc)) from exc

    chosen = {item for item in analysis_id if item}
    # A named result may live on an older population: the researcher asked for it by
    # name, so it is looked up across the table's populations and marked stale, rather
    # than reported as missing.
    by_population = {item.id: item for item in populations}
    if chosen:
        candidates = [
            (analysis, by_population[analysis.population_id])
            for item in populations
            for analysis in crud.list_analyses(db, item.id)
        ]
    else:
        candidates = [
            (analysis, population) for analysis in crud.list_analyses(db, population.id)
        ]

    analyses: list[dict] = []
    for analysis, owner in candidates:
        if chosen and analysis.id not in chosen:
            continue
        if not chosen and crud.analysis_is_stale(analysis, owner):
            continue
        analyses.append(_analysis_response(analysis, owner).model_dump())
    missing = chosen - {analysis["id"] for analysis in analyses}
    if missing:
        raise _not_found("Analysis not found: " + ", ".join(sorted(missing)))

    quality_report = quality.audit(frame, _config(table))
    steps = [
        {
            "seq": step.seq,
            "kind": step.kind,
            "params": json.loads(step.params_json or "{}"),
            "data": json.loads(step.data_json or "{}"),
        }
        for step in crud.list_steps(db, table.id)
    ]
    project = get_project(db, project_id)
    document = dossier.build_dossier(
        table=_table_response(table).model_dump(),
        project={"id": project_id, "name": project.name if project else project_id},
        versions=[
            _version_response(item).model_dump()
            for item in reversed(crud.list_versions(db, table.id))
        ],
        population=_population_response(population).model_dump(),
        flow=_build_flow(table, population),
        quality=quality_report.to_dict(),
        steps=steps,
        analyses=analyses,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    filename = f"study-dossier-{table.name}.docx".replace(" ", "_")
    return Response(
        content=document,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
