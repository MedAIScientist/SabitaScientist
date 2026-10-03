"""Experiment endpoints — CRUD, task linking, and entry management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel as _BaseModel

from ...crud.experiment_assets import (
    asset_exists,
    asset_project_id,
    count_assets_by_experiment,
    dataset_available_to_project,
    link_asset,
    list_assets,
    list_project_assets,
    unlink_asset,
)
from ...crud.experiment_entries import (
    create_entry,
    delete_entry,
    get_entry,
    list_entries,
    update_entry,
)
from ...crud.experiment_metrics import (
    create_metrics,
    delete_metric,
    list_metrics,
)
from ...crud.experiments import (
    create_experiment,
    delete_experiment,
    get_experiment,
    link_task,
    list_experiments,
    list_experiments_for_task,
    list_linked_tasks,
    unlink_task,
    update_experiment,
)
from ...crud.tasks import get_task
from ...db import get_db_path
from ...metrics_csv import ParsedMetric
from ...models import User
from ..deps import require_project_role
from ..schemas import (
    ExperimentAssetCreate,
    ExperimentAssetResponse,
    ExperimentCreate,
    ExperimentEntryCreate,
    ExperimentEntryResponse,
    ExperimentEntryUpdate,
    ExperimentMetricCreate,
    ExperimentMetricResponse,
    ExperimentResponse,
    ExperimentUpdate,
    ProjectAssetLink,
    TaskResponse,
)

router = APIRouter()


class _LinkTaskBody(_BaseModel):
    task_id: str


def _exp_to_response(e, asset_count: int | None = None) -> ExperimentResponse:
    return ExperimentResponse(
        id=e.id,
        project_id=e.project_id,
        name=e.name,
        hypothesis=e.hypothesis,
        protocol=e.protocol,
        status=e.status,
        tags=e.tags,
        deadline=e.deadline,
        created_by=e.created_by,
        created_at=e.created_at,
        updated_at=e.updated_at,
        phase_id=e.phase_id,
        linked_task_count=_count_linked_tasks(e.id),
        linked_asset_count=(
            _count_linked_assets(e.id) if asset_count is None else asset_count
        ),
    )


def _count_linked_assets(exp_id: str) -> int:
    return count_assets_by_experiment(get_db_path(), [exp_id]).get(exp_id, 0)


def _asset_to_response(a) -> ExperimentAssetResponse:
    return ExperimentAssetResponse(
        experiment_id=a.experiment_id,
        asset_type=a.asset_type,
        asset_id=a.asset_id,
        role=a.role,
        note=a.note,
        linked_at=a.linked_at,
        linked_by=a.linked_by,
        label=a.label,
        detail=a.detail,
    )


def _count_linked_tasks(exp_id: str) -> int:
    from ...db import get_db

    with get_db(get_db_path()) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM experiment_tasks WHERE experiment_id = ?", (exp_id,)
        ).fetchone()
        return int(row[0]) if row else 0


def _entry_to_response(e) -> ExperimentEntryResponse:
    return ExperimentEntryResponse(
        id=e.id,
        experiment_id=e.experiment_id,
        type=e.type,
        title=e.title,
        body=e.body,
        author_id=e.author_id,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


def _task_to_response(t) -> TaskResponse:
    return TaskResponse(
        id=t.id,
        project_id=t.project_id,
        title=t.title,
        description=t.description,
        assignee_id=t.assignee_id,
        status=t.status,
        priority=t.priority,
        deadline=t.deadline,
        session_id=t.session_id,
        created_by=t.created_by,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _get_exp_or_404(project_id: str, exp_id: str):
    """Return experiment or raise 404 if missing or wrong project."""
    exp = get_experiment(get_db_path(), exp_id)
    if not exp or exp.project_id != project_id:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


# ── Experiment CRUD ──────────────────────────────────────────────────────────


@router.post(
    "/{project_id}/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_experiment(
    project_id: str,
    body: ExperimentCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Create a new experiment in the project."""
    exp = create_experiment(
        get_db_path(),
        project_id=project_id,
        name=body.name,
        created_by=current_user.id,
        hypothesis=body.hypothesis,
        protocol=body.protocol,
        status=body.status,
        tags=body.tags,
        deadline=body.deadline,
        phase_id=body.phase_id,
    )
    return _exp_to_response(exp)


@router.get("/{project_id}/experiments", response_model=list[ExperimentResponse])
def list_project_experiments(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List all experiments for a project."""
    db = get_db_path()
    experiments = list_experiments(db, project_id)
    # One grouped count for the whole page instead of a query per row.
    asset_counts = count_assets_by_experiment(db, [e.id for e in experiments])
    return [_exp_to_response(e, asset_counts.get(e.id, 0)) for e in experiments]


@router.get("/{project_id}/experiments/{exp_id}", response_model=ExperimentResponse)
def get_experiment_detail(
    project_id: str,
    exp_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """Get a single experiment."""
    return _exp_to_response(_get_exp_or_404(project_id, exp_id))


@router.patch("/{project_id}/experiments/{exp_id}", response_model=ExperimentResponse)
def patch_experiment(
    project_id: str,
    exp_id: str,
    body: ExperimentUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Update experiment fields."""
    _get_exp_or_404(project_id, exp_id)
    # Use model_fields_set to only update fields explicitly provided in the request.
    # This prevents accidentally clearing name when it was not included in the payload.
    provided = body.model_fields_set
    kwargs: dict = {}
    if "name" in provided and body.name is not None:
        kwargs["name"] = body.name
    if "hypothesis" in provided:
        kwargs["hypothesis"] = body.hypothesis
    if "protocol" in provided:
        kwargs["protocol"] = body.protocol
    if "status" in provided:
        kwargs["status"] = body.status
    if "tags" in provided:
        kwargs["tags"] = body.tags
    if "deadline" in provided:
        kwargs["deadline"] = body.deadline
    # phase_id is what puts an experiment in a board swimlane. It was missing from
    # this chain, so the UI's phase dropdown and the board's bulk "set phase"
    # silently did nothing while still returning 200.
    if "phase_id" in provided:
        kwargs["phase_id"] = body.phase_id
    updated = update_experiment(get_db_path(), exp_id, **kwargs)
    return _exp_to_response(updated)


@router.delete(
    "/{project_id}/experiments/{exp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_experiment_endpoint(
    project_id: str,
    exp_id: str,
    current_user: User = Depends(require_project_role("owner")),
):
    """Delete an experiment (cascades to entries and task links)."""
    _get_exp_or_404(project_id, exp_id)
    delete_experiment(get_db_path(), exp_id)


# ── Task linking ─────────────────────────────────────────────────────────────


@router.post(
    "/{project_id}/experiments/{exp_id}/tasks",
    status_code=status.HTTP_201_CREATED,
)
def link_task_to_experiment(
    project_id: str,
    exp_id: str,
    body: _LinkTaskBody,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Link a task to an experiment.

    The experiment automatically moves to the linked task's phase so it
    appears in the same swimlane on the Kanban board.
    """
    exp = _get_exp_or_404(project_id, exp_id)
    task = get_task(get_db_path(), body.task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(
            status_code=422, detail="Task does not belong to this project"
        )
    try:
        link_task(get_db_path(), exp_id, body.task_id, linked_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # Sync experiment phase to the linked task's phase
    if task.phase_id and task.phase_id != exp.phase_id:
        update_experiment(get_db_path(), exp_id, phase_id=task.phase_id)
    return {
        "experiment_id": exp_id,
        "task_id": body.task_id,
        "phase_id": task.phase_id,
    }


@router.delete(
    "/{project_id}/experiments/{exp_id}/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_task_from_experiment(
    project_id: str,
    exp_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Unlink a task from an experiment."""
    _get_exp_or_404(project_id, exp_id)
    unlink_task(get_db_path(), exp_id, task_id)


@router.get(
    "/{project_id}/experiments/{exp_id}/tasks",
    response_model=list[TaskResponse],
)
def get_linked_tasks(
    project_id: str,
    exp_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List all tasks linked to an experiment."""
    _get_exp_or_404(project_id, exp_id)
    return [_task_to_response(t) for t in list_linked_tasks(get_db_path(), exp_id)]


@router.get(
    "/{project_id}/tasks/{task_id}/experiments",
    response_model=list[ExperimentResponse],
)
def get_experiments_for_task(
    project_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List all experiments linked to a task (reverse of task linking)."""
    from ...crud.tasks import get_task as _get_task

    task = _get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return [
        _exp_to_response(e) for e in list_experiments_for_task(get_db_path(), task_id)
    ]


# ── Entries ───────────────────────────────────────────────────────────────────


@router.get(
    "/{project_id}/experiments/{exp_id}/entries",
    response_model=list[ExperimentEntryResponse],
)
def list_experiment_entries(
    project_id: str,
    exp_id: str,
    type: str | None = Query(default=None, pattern="^(note|result)$"),
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List entries for an experiment. Optionally filter by ?type=note|result."""
    _get_exp_or_404(project_id, exp_id)
    return [_entry_to_response(e) for e in list_entries(get_db_path(), exp_id, type)]


@router.post(
    "/{project_id}/experiments/{exp_id}/entries",
    response_model=ExperimentEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_experiment_entry(
    project_id: str,
    exp_id: str,
    body: ExperimentEntryCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Create a note or result entry on an experiment."""
    _get_exp_or_404(project_id, exp_id)
    entry = create_entry(
        get_db_path(),
        experiment_id=exp_id,
        entry_type=body.type,
        title=body.title,
        body=body.body,
        author_id=current_user.id,
    )
    return _entry_to_response(entry)


@router.patch(
    "/{project_id}/experiments/{exp_id}/entries/{entry_id}",
    response_model=ExperimentEntryResponse,
)
def patch_experiment_entry(
    project_id: str,
    exp_id: str,
    entry_id: str,
    body: ExperimentEntryUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Update an entry's title and/or body."""
    _get_exp_or_404(project_id, exp_id)
    entry = get_entry(get_db_path(), entry_id)
    if not entry or entry.experiment_id != exp_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    updated = update_entry(get_db_path(), entry_id, title=body.title, body=body.body)
    return _entry_to_response(updated)


@router.delete(
    "/{project_id}/experiments/{exp_id}/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_experiment_entry(
    project_id: str,
    exp_id: str,
    entry_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Delete an entry."""
    _get_exp_or_404(project_id, exp_id)
    entry = get_entry(get_db_path(), entry_id)
    if not entry or entry.experiment_id != exp_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    delete_entry(get_db_path(), entry_id)


# ── Metrics ───────────────────────────────────────────────────────────────────


def _metric_to_response(m) -> ExperimentMetricResponse:
    return ExperimentMetricResponse(
        id=m.id,
        experiment_id=m.experiment_id,
        name=m.name,
        value=m.value,
        unit=m.unit,
        split=m.split,
        n=m.n,
        stderr=m.stderr,
        source_attachment_id=m.source_attachment_id,
        recorded_by=m.recorded_by,
        created_at=m.created_at,
    )


@router.get(
    "/{project_id}/experiments/{exp_id}/metrics",
    response_model=list[ExperimentMetricResponse],
    summary="List recorded numeric results for an experiment",
)
def list_experiment_metrics(
    project_id: str,
    exp_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """Return every recorded metric. These are the only numbers AI drafting sees."""
    _get_exp_or_404(project_id, exp_id)
    return [_metric_to_response(m) for m in list_metrics(get_db_path(), exp_id)]


@router.post(
    "/{project_id}/experiments/{exp_id}/metrics",
    response_model=ExperimentMetricResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a numeric result by hand",
)
def create_experiment_metric(
    project_id: str,
    exp_id: str,
    body: ExperimentMetricCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Record one metric manually, for results that never arrive as a CSV."""
    _get_exp_or_404(project_id, exp_id)
    created = create_metrics(
        get_db_path(),
        experiment_id=exp_id,
        metrics=[
            ParsedMetric(
                name=body.name,
                value=body.value,
                unit=body.unit,
                split=body.split,
                n=body.n,
                stderr=body.stderr,
            )
        ],
        recorded_by=current_user.id,
    )
    return _metric_to_response(created[0])


@router.delete(
    "/{project_id}/experiments/{exp_id}/metrics/{metric_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a recorded metric",
)
def delete_experiment_metric(
    project_id: str,
    exp_id: str,
    metric_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Delete a metric that was recorded in error."""
    _get_exp_or_404(project_id, exp_id)
    if not any(m.id == metric_id for m in list_metrics(get_db_path(), exp_id)):
        raise HTTPException(status_code=404, detail="Metric not found")
    delete_metric(get_db_path(), metric_id)


# ── Data lineage: the assets an experiment consumed and produced ──────────────


def _require_linkable_asset(
    db, project_id: str, asset_type: str, asset_id: str
) -> None:
    """422/404 unless the asset exists and this project may reference it.

    Project-owned assets must belong to the experiment's own project, so a link
    cannot be used to reach across projects. Datasets are lab-owned, so the test
    there is an active grant to this project instead.
    """
    if not asset_exists(db, asset_type, asset_id):
        raise HTTPException(status_code=404, detail=f"{asset_type} not found")
    if asset_type == "dataset":
        if not dataset_available_to_project(db, asset_id, project_id):
            raise HTTPException(
                status_code=422,
                detail="Dataset is not granted to this project",
            )
        return
    owner = asset_project_id(db, asset_type, asset_id)
    if owner != project_id:
        raise HTTPException(
            status_code=422, detail=f"{asset_type} does not belong to this project"
        )


@router.get(
    "/{project_id}/experiments/{exp_id}/assets",
    response_model=list[ExperimentAssetResponse],
    summary="Data lineage for an experiment",
)
def list_experiment_assets(
    project_id: str,
    exp_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """Inputs, processing runs and produced artefacts linked to this experiment."""
    _get_exp_or_404(project_id, exp_id)
    return [_asset_to_response(a) for a in list_assets(get_db_path(), exp_id)]


@router.post(
    "/{project_id}/experiments/{exp_id}/assets",
    response_model=ExperimentAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Link a dataset, pipeline run, annotation or sandbox to an experiment",
)
def link_experiment_asset(
    project_id: str,
    exp_id: str,
    body: ExperimentAssetCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Attach one asset to an experiment. Re-linking updates its role."""
    _get_exp_or_404(project_id, exp_id)
    db = get_db_path()
    _require_linkable_asset(db, project_id, body.asset_type, body.asset_id)
    link_asset(
        db,
        experiment_id=exp_id,
        asset_type=body.asset_type,
        asset_id=body.asset_id,
        role=body.role,
        note=body.note,
        linked_by=current_user.id,
    )
    # Re-read so the response carries the resolved label like the list does.
    linked = next(
        a
        for a in list_assets(db, exp_id)
        if a.asset_type == body.asset_type and a.asset_id == body.asset_id
    )
    return _asset_to_response(linked)


@router.delete(
    "/{project_id}/experiments/{exp_id}/assets/{asset_type}/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink an asset from an experiment",
)
def unlink_experiment_asset(
    project_id: str,
    exp_id: str,
    asset_type: str,
    asset_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Remove a lineage link. The asset itself is untouched."""
    _get_exp_or_404(project_id, exp_id)
    if not unlink_asset(get_db_path(), exp_id, asset_type, asset_id):
        raise HTTPException(status_code=404, detail="Link not found")


@router.get(
    "/{project_id}/experiment-assets",
    response_model=list[ProjectAssetLink],
    summary="Which experiments reference which assets in this project",
)
def list_project_asset_links(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """Reverse lineage for the project data view: asset -> experiments using it.

    Returned flat and grouped client-side so the view costs one request.
    """
    return [
        ProjectAssetLink(**row)
        for row in list_project_assets(get_db_path(), project_id)
    ]
