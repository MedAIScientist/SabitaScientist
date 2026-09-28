"""Bulk task operations — update status, priority, assignee, phase for many tasks at once."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...crud.projects import get_project
from ...crud.task_history import record_task_change
from ...db import get_db, get_db_path
from ...models import User
from ..deps import require_project_role

router = APIRouter()


class BulkTaskUpdateRequest(BaseModel):
    task_ids: list[str] = Field(min_length=1, max_length=100)
    status: str | None = Field(default=None, pattern=r"^(todo|in_progress|done)$")
    priority: str | None = Field(default=None, pattern=r"^(critical|high|medium|low)$")
    assignee_id: str | None = None
    phase_id: str | None = None


@router.post("/projects/{project_id}/tasks/bulk", status_code=status.HTTP_200_OK)
def bulk_update_tasks(
    project_id: str,
    body: BulkTaskUpdateRequest,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    p = get_project(get_db_path(), project_id)
    if not p:
        raise HTTPException(404, "Project not found")

    sets = {}
    if body.status is not None:
        sets["status"] = body.status
    if body.priority is not None:
        sets["priority"] = body.priority
    if body.assignee_id is not None:
        sets["assignee_id"] = body.assignee_id
    if body.phase_id is not None:
        sets["phase_id"] = body.phase_id

    if not sets:
        raise HTTPException(400, "No fields to update")

    clause = ", ".join(f"{k} = ?" for k in sets)
    placeholders = ",".join("?" for _ in body.task_ids)

    with get_db(get_db_path()) as conn:
        conn.execute(
            f"UPDATE tasks SET {clause}, updated_at = datetime('now') WHERE id IN ({placeholders}) AND project_id = ?",
            [*sets.values(), *body.task_ids, project_id],
        )
        if body.status is not None:
            for tid in body.task_ids:
                record_task_change(conn, tid, current_user.id, "status", to_status=body.status)

    return {"updated": len(body.task_ids)}
