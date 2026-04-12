"""Task and comment routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.dependencies import get_blocked_by
from ...crud.tasks import (
    create_comment,
    create_task,
    delete_comment,
    delete_task,
    get_task,
    list_comments,
    list_tasks,
    update_task,
)
from ...db import get_db_path
from ...models import User
from ..deps import require_project_role
from ..schemas import (
    CommentCreate,
    CommentResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)

router = APIRouter()


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
        phase_id=getattr(t, "phase_id", None),
        # NOTE: issues one extra query per task (N+1). Acceptable for current SQLite/low-volume usage.
        blocked_by=get_blocked_by(get_db_path(), t.id),
    )


@router.get("/{project_id}/tasks", response_model=list[TaskResponse])
def list_project_tasks(
    project_id: str,
    status_filter: str | None = None,
    assignee_id: str | None = None,
    priority: str | None = None,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List tasks for a project with optional filters."""
    tasks = list_tasks(
        get_db_path(),
        project_id,
        status=status_filter,
        assignee_id=assignee_id,
        priority=priority,
    )
    return [_task_to_response(t) for t in tasks]


@router.post(
    "/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_task(
    project_id: str,
    body: TaskCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Create a task (owner/editor only)."""
    task = create_task(
        get_db_path(),
        project_id=project_id,
        title=body.title,
        created_by=current_user.id,
        description=body.description,
        assignee_id=body.assignee_id,
        priority=body.priority,
        deadline=body.deadline,
        session_id=body.session_id,
    )
    return _task_to_response(task)


@router.get("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
def get_task_detail(
    project_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """Get a task by ID."""
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_response(task)


@router.put("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
def update_existing_task(
    project_id: str,
    task_id: str,
    body: TaskUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Update a task (owner/editor only)."""
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    updated = update_task(
        get_db_path(),
        task_id,
        title=body.title,
        description=body.description,
        assignee_id=body.assignee_id,
        status=body.status,
        priority=body.priority,
        deadline=body.deadline,
        session_id=body.session_id,
    )
    return _task_to_response(updated)


@router.delete("/{project_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_task(
    project_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Delete a task (owner/editor only)."""
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    delete_task(get_db_path(), task_id)


@router.get(
    "/{project_id}/tasks/{task_id}/comments", response_model=list[CommentResponse]
)
def get_comments(
    project_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List comments for a task."""
    return [
        CommentResponse(
            id=c.id,
            task_id=c.task_id,
            author_id=c.author_id,
            body=c.body,
            created_at=c.created_at,
        )
        for c in list_comments(get_db_path(), task_id)
    ]


@router.post(
    "/{project_id}/tasks/{task_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    project_id: str,
    task_id: str,
    body: CommentCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Add a comment to a task (owner/editor only)."""
    comment = create_comment(
        get_db_path(), task_id=task_id, body=body.body, author_id=current_user.id
    )
    return CommentResponse(
        id=comment.id,
        task_id=comment.task_id,
        author_id=comment.author_id,
        body=comment.body,
        created_at=comment.created_at,
    )


@router.delete(
    "/{project_id}/tasks/{task_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_comment(
    project_id: str,
    task_id: str,
    comment_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Delete a comment (owner/editor only)."""
    delete_comment(get_db_path(), comment_id)
