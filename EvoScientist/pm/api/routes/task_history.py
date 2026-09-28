"""Task history — audit trail for task status changes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...crud.task_history import list_task_history
from ...crud.tasks import get_task
from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user

router = APIRouter()


@router.get("/projects/{project_id}/tasks/{task_id}/history")
def get_task_history(
    project_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    t = get_task(get_db_path(), task_id)
    if not t or t.project_id != project_id:
        raise HTTPException(404, "Task not found")
    with get_db(get_db_path()) as conn:
        return [
            {
                "id": h.id,
                "changed_by": h.changed_by,
                "from_status": h.from_status,
                "to_status": h.to_status,
                "change_type": h.change_type,
                "comment": h.comment,
                "created_at": h.created_at,
            }
            for h in list_task_history(conn, task_id)
        ]
