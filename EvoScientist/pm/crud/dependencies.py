"""CRUD operations for TaskDependency entities, including cycle detection."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import TaskDependency

_VALID_DEP_TYPES = {"hard", "soft"}


def _row_to_dependency(row) -> TaskDependency:
    return TaskDependency(
        task_id=row["task_id"],
        depends_on_id=row["depends_on_id"],
        dep_type=row["dep_type"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _has_cycle(conn: sqlite3.Connection, start_task_id: str) -> bool:
    """Return True if start_task_id is reachable from itself via dependency edges.

    Reads the full task_dependencies graph from the given connection and uses an
    iterative DFS.  The new edge has already been INSERTed when this is called,
    so it is naturally included in the graph.
    """
    # Build adjacency list: task_id -> list of depends_on_id
    rows = conn.execute(
        "SELECT task_id, depends_on_id FROM task_dependencies"
    ).fetchall()
    graph: dict[str, list[str]] = {}
    for row in rows:
        graph.setdefault(row["task_id"], []).append(row["depends_on_id"])

    # DFS starting from the nodes that start_task_id depends on (i.e., its neighbours)
    # A cycle exists if we can reach start_task_id from itself.
    visited: set[str] = set()
    stack = list(graph.get(start_task_id, []))
    while stack:
        node = stack.pop()
        if node == start_task_id:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(graph.get(node, []))
    return False


def add_dependency(
    db_path: Path,
    task_id: str,
    depends_on_id: str,
    dep_type: str,
    created_by: str,
) -> TaskDependency:
    """Insert a new task dependency and return it.

    Raises:
        ValueError: If dep_type is invalid, task_id == depends_on_id, or a cycle
            would be created.
    """
    if dep_type not in _VALID_DEP_TYPES:
        raise ValueError(f"dep_type must be one of {_VALID_DEP_TYPES!r}, got {dep_type!r}")
    if task_id == depends_on_id:
        raise ValueError("A task cannot depend on itself")

    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO task_dependencies
               (task_id, depends_on_id, dep_type, created_by, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, depends_on_id, dep_type, created_by, now),
        )
        if _has_cycle(conn, task_id):
            raise ValueError("Adding this dependency would create a cycle")

    return TaskDependency(
        task_id=task_id,
        depends_on_id=depends_on_id,
        dep_type=dep_type,
        created_by=created_by,
        created_at=now,
    )


def remove_dependency(db_path: Path, task_id: str, depends_on_id: str) -> bool:
    """Delete a dependency row.

    Returns:
        True if a row was deleted, False if it did not exist.
    """
    with get_db(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM task_dependencies WHERE task_id = ? AND depends_on_id = ?",
            (task_id, depends_on_id),
        )
    return cur.rowcount > 0


def list_dependencies(db_path: Path, task_id: str) -> list[TaskDependency]:
    """Return all dependencies for a task (tasks that *task_id* depends on)."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM task_dependencies WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
    return [_row_to_dependency(r) for r in rows]


def list_dependents(db_path: Path, task_id: str) -> list[TaskDependency]:
    """Return all dependency rows where *task_id* is the depended-upon task.

    These are the tasks that depend ON the given task_id.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM task_dependencies WHERE depends_on_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
    return [_row_to_dependency(r) for r in rows]


def get_blocked_by(db_path: Path, task_id: str) -> list[str]:
    """Return task IDs that hard-block the given task.

    Only 'hard' dependency types are included.  Used to populate ``blocked_by``
    on API responses.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT depends_on_id FROM task_dependencies
               WHERE task_id = ? AND dep_type = 'hard'
               ORDER BY created_at""",
            (task_id,),
        ).fetchall()
    return [row["depends_on_id"] for row in rows]
