"""Dependency routes for task workflow coordination."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.dependencies import (
    add_dependency,
    list_dependencies,
    list_dependents,
    remove_dependency,
)
from ...crud.projects import get_member_role
from ...crud.tasks import get_task
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user
from ..schemas import (
    DependenciesListResponse,
    DependencyCreate,
    DependencyResponse,
)

router = APIRouter()


def _check_project_membership(project_id: str, user: User) -> None:
    """Raise 403 if user is not owner/editor in the project."""
    role = get_member_role(get_db_path(), project_id, user.id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member"
        )


def _check_project_editor(project_id: str, user: User) -> None:
    """Raise 403 if user is not owner/editor in the project."""
    role = get_member_role(get_db_path(), project_id, user.id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member"
        )
    if role not in ("owner", "editor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' not permitted here",
        )


def _dep_to_response(d) -> DependencyResponse:
    return DependencyResponse(
        task_id=d.task_id,
        depends_on_id=d.depends_on_id,
        dep_type=d.dep_type,
        created_by=d.created_by,
        created_at=d.created_at,
    )


@router.post(
    "/{project_id}/tasks/{task_id}/dependencies",
    response_model=DependencyResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_task_dependency(
    project_id: str,
    task_id: str,
    body: DependencyCreate,
    current_user: User = Depends(get_current_user),
):
    """Add a dependency to a task (owner/editor only)."""
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    _check_project_editor(project_id, current_user)
    try:
        dep = add_dependency(
            get_db_path(),
            task_id=task_id,
            depends_on_id=body.depends_on_id,
            dep_type=body.dep_type,
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _dep_to_response(dep)


@router.delete(
    "/{project_id}/tasks/{task_id}/dependencies/{dep_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_task_dependency(
    project_id: str,
    task_id: str,
    dep_id: str,
    current_user: User = Depends(get_current_user),
):
    """Remove a dependency from a task (owner/editor only)."""
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    _check_project_editor(project_id, current_user)
    deleted = remove_dependency(get_db_path(), task_id=task_id, depends_on_id=dep_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dependency not found")


@router.get(
    "/{project_id}/tasks/{task_id}/dependencies",
    response_model=DependenciesListResponse,
)
def list_task_dependencies(
    project_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """List all dependencies for a task in both directions."""
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    _check_project_membership(project_id, current_user)
    deps = list_dependencies(get_db_path(), task_id)
    dependents = list_dependents(get_db_path(), task_id)
    return DependenciesListResponse(
        dependencies=[_dep_to_response(d) for d in deps],
        dependents=[_dep_to_response(d) for d in dependents],
    )
