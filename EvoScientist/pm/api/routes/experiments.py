"""Experiment endpoints — CRUD, task linking, and entry management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel as _BaseModel

from ...crud.experiment_entries import (
    create_entry,
    delete_entry,
    get_entry,
    list_entries,
    update_entry,
)
from ...crud.experiments import (
    create_experiment,
    delete_experiment,
    get_experiment,
    link_task,
    list_experiments,
    list_linked_tasks,
    unlink_task,
    update_experiment,
)
from ...crud.tasks import get_task
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import (
    ExperimentCreate,
    ExperimentEntryCreate,
    ExperimentEntryResponse,
    ExperimentEntryUpdate,
    ExperimentResponse,
    ExperimentUpdate,
    TaskResponse,
)

router = APIRouter()


class _LinkTaskBody(_BaseModel):
    task_id: str


def _exp_to_response(e) -> ExperimentResponse:
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
    )


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
    )
    return _exp_to_response(exp)


@router.get("/{project_id}/experiments", response_model=list[ExperimentResponse])
def list_project_experiments(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List all experiments for a project."""
    return [_exp_to_response(e) for e in list_experiments(get_db_path(), project_id)]


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
    """Link a task to an experiment."""
    _get_exp_or_404(project_id, exp_id)
    task = get_task(get_db_path(), body.task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=422, detail="Task does not belong to this project")
    try:
        link_task(get_db_path(), exp_id, body.task_id, linked_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"experiment_id": exp_id, "task_id": body.task_id}


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
