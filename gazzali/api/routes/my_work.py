"""The signed-in user's own work across projects (student dashboard)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user

router = APIRouter()


@router.get("/me/tasks")
def my_open_tasks(current_user: User = Depends(get_current_user)):
    """Open tasks assigned to me, soonest deadline first (tasks without one last).

    Only projects I am still a member of: a task left behind in a project I was
    removed from is not mine to act on.
    """
    with get_db(get_db_path()) as conn:
        rows = conn.execute(
            """SELECT t.id, t.title, t.status, t.priority, t.deadline, t.project_id, p.name AS project_name
                 FROM tasks t
                 JOIN projects p ON p.id = t.project_id AND p.archived_at IS NULL
                 JOIN project_members m ON m.project_id = t.project_id AND m.user_id = ?
                WHERE t.assignee_id = ? AND t.status != 'done'
                ORDER BY t.deadline IS NULL, t.deadline, t.created_at""",
            (current_user.id, current_user.id),
        ).fetchall()
    return [dict(r) for r in rows]
