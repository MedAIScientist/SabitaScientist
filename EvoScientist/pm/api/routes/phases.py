"""Phase routes for project workflow coordination."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.phases import (
    assign_task_phase,
    create_phase,
    delete_phase,
    get_phase,
    list_phases,
    update_phase,
)
from ...db import get_db_path
from ...models import User
from ..deps import require_project_role
from ..schemas import (
    AssignPhaseRequest,
    PhaseCreate,
    PhaseResponse,
    PhaseUpdate,
)

router = APIRouter()


def _phase_to_response(p) -> PhaseResponse:
    return PhaseResponse(
        id=p.id,
        project_id=p.project_id,
        name=p.name,
        color=p.color,
        position=p.position,
        target_date=p.target_date,
        created_by=p.created_by,
        created_at=p.created_at,
    )


@router.get("/{project_id}/phases", response_model=list[PhaseResponse])
def list_project_phases(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List phases for a project ordered by position."""
    phases = list_phases(get_db_path(), project_id)
    return [_phase_to_response(p) for p in phases]


@router.post(
    "/{project_id}/phases",
    response_model=PhaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_phase(
    project_id: str,
    body: PhaseCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Create a phase (owner/editor only)."""
    phase = create_phase(
        get_db_path(),
        project_id=project_id,
        name=body.name,
        color=body.color,
        position=body.position,
        target_date=body.target_date,
        created_by=current_user.id,
    )
    return _phase_to_response(phase)


@router.get("/{project_id}/phases/{phase_id}", response_model=PhaseResponse)
def get_phase_detail(
    project_id: str,
    phase_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """Get a phase by ID."""
    phase = get_phase(get_db_path(), phase_id)
    if not phase or phase.project_id != project_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    return _phase_to_response(phase)


@router.patch("/{project_id}/phases/{phase_id}", response_model=PhaseResponse)
def update_existing_phase(
    project_id: str,
    phase_id: str,
    body: PhaseUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Update a phase (owner/editor only)."""
    phase = get_phase(get_db_path(), phase_id)
    if not phase or phase.project_id != project_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = update_phase(get_db_path(), phase_id, **kwargs)
    return _phase_to_response(updated)


@router.delete("/{project_id}/phases/{phase_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_phase(
    project_id: str,
    phase_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Delete a phase (owner/editor only)."""
    phase = get_phase(get_db_path(), phase_id)
    if not phase or phase.project_id != project_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    delete_phase(get_db_path(), phase_id)


@router.post("/{project_id}/phases/{phase_id}/assign-task", response_model=dict)
def assign_task_to_phase(
    project_id: str,
    phase_id: str,
    body: AssignPhaseRequest,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Assign or unassign a task to a phase (owner/editor only)."""
    phase = get_phase(get_db_path(), phase_id)
    if not phase or phase.project_id != project_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    assign_task_phase(get_db_path(), task_id=body.task_id, phase_id=body.phase_id)
    return {"ok": True}
