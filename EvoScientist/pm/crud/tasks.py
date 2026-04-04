"""CRUD operations for Task and Comment entities."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Comment, Task


def create_task(
    db_path: Path,
    project_id: str,
    title: str,
    created_by: str,
    description: str | None = None,
    assignee_id: str | None = None,
    priority: str = "medium",
    deadline: str | None = None,
    session_id: str | None = None,
) -> Task:
    """Create a task and return it."""
    task_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO tasks
               (id, project_id, title, description, assignee_id, status, priority,
                deadline, session_id, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'todo', ?, ?, ?, ?, ?, ?)""",
            (task_id, project_id, title, description, assignee_id, priority,
             deadline, session_id, created_by, now, now),
        )
    return Task(
        id=task_id,
        project_id=project_id,
        title=title,
        description=description,
        assignee_id=assignee_id,
        status="todo",
        priority=priority,
        deadline=deadline,
        session_id=session_id,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def get_task(db_path: Path, task_id: str) -> Task | None:
    """Return Task by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_task(row) if row else None


def list_tasks(
    db_path: Path,
    project_id: str,
    status: str | None = None,
    assignee_id: str | None = None,
    priority: str | None = None,
) -> list[Task]:
    """Return tasks for a project, with optional filters."""
    query = "SELECT * FROM tasks WHERE project_id = ?"
    params: list = [project_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    if assignee_id:
        query += " AND assignee_id = ?"
        params.append(assignee_id)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    query += " ORDER BY created_at ASC"
    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_task(r) for r in rows]


def update_task(
    db_path: Path,
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    assignee_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    deadline: str | None = None,
    session_id: str | None = None,
) -> Task:
    """Update task fields. Omitted fields are unchanged."""
    task = get_task(db_path, task_id)
    if task is None:
        raise ValueError(f"Task {task_id!r} not found")
    now = datetime.now(UTC).isoformat()
    new = Task(
        id=task.id,
        project_id=task.project_id,
        title=title if title is not None else task.title,
        description=description if description is not None else task.description,
        assignee_id=assignee_id if assignee_id is not None else task.assignee_id,
        status=status if status is not None else task.status,
        priority=priority if priority is not None else task.priority,
        deadline=deadline if deadline is not None else task.deadline,
        session_id=session_id if session_id is not None else task.session_id,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=now,
    )
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE tasks SET title=?, description=?, assignee_id=?, status=?,
               priority=?, deadline=?, session_id=?, updated_at=? WHERE id=?""",
            (new.title, new.description, new.assignee_id, new.status,
             new.priority, new.deadline, new.session_id, now, task_id),
        )
    return new


def delete_task(db_path: Path, task_id: str) -> bool:
    """Delete a task and cascade to comments. Returns True if deleted."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return cur.rowcount > 0


def create_comment(
    db_path: Path, task_id: str, body: str, author_id: str | None = None
) -> Comment:
    """Add a comment to a task."""
    comment_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO task_comments (id, task_id, author_id, body, created_at) VALUES (?, ?, ?, ?, ?)",
            (comment_id, task_id, author_id, body, now),
        )
    return Comment(id=comment_id, task_id=task_id, author_id=author_id, body=body, created_at=now)


def list_comments(db_path: Path, task_id: str) -> list[Comment]:
    """Return comments for a task, oldest first."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, task_id, author_id, body, created_at FROM task_comments WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        ).fetchall()
    return [Comment(id=r["id"], task_id=r["task_id"], author_id=r["author_id"], body=r["body"], created_at=r["created_at"]) for r in rows]


def delete_comment(db_path: Path, comment_id: str) -> bool:
    """Delete a comment by id. Returns True if deleted."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM task_comments WHERE id = ?", (comment_id,))
    return cur.rowcount > 0


def _row_to_task(row) -> Task:
    return Task(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        description=row["description"],
        assignee_id=row["assignee_id"],
        status=row["status"],
        priority=row["priority"],
        deadline=row["deadline"],
        session_id=row["session_id"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
