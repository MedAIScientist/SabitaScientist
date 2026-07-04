"""CRUD operations for Project and Member entities."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Member, Project


def create_project(
    db_path: Path,
    name: str,
    created_by: str,
    description: str | None = None,
    lab_id: str | None = None,
) -> Project:
    """Create a project and automatically add creator as owner."""
    project_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, created_by, created_at, lab_id) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, name, description, created_by, now, lab_id),
        )
        conn.execute(
            "INSERT INTO project_members (project_id, user_id, role, added_at) VALUES (?, ?, ?, ?)",
            (project_id, created_by, "owner", now),
        )
    return Project(
        id=project_id,
        name=name,
        description=description,
        created_by=created_by,
        created_at=now,
        lab_id=lab_id,
    )


def get_project(db_path: Path, project_id: str) -> Project | None:
    """Return Project by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, name, description, created_by, created_at, archived_at FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    return _row_to_project(row) if row else None


def list_projects_for_user(
    db_path: Path, user_id: str, lab_id: str | None = None
) -> list[Project]:
    """Return all non-archived projects the user is a member of, optionally filtered by lab."""
    query = """SELECT p.id, p.name, p.description, p.created_by, p.created_at, p.archived_at
               FROM projects p
               JOIN project_members pm ON p.id = pm.project_id
               WHERE pm.user_id = ? AND p.archived_at IS NULL"""
    params: list = [user_id]
    if lab_id:
        query += " AND p.lab_id = ?"
        params.append(lab_id)
    query += " ORDER BY p.created_at DESC"
    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_project(r) for r in rows]


def add_member(db_path: Path, project_id: str, user_id: str, role: str) -> Member:
    """Add a user to a project with the given role."""
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO project_members (project_id, user_id, role, added_at) VALUES (?, ?, ?, ?)",
            (project_id, user_id, role, now),
        )
    return Member(project_id=project_id, user_id=user_id, role=role, added_at=now)


def remove_member(db_path: Path, project_id: str, user_id: str) -> bool:
    """Remove a user from a project. Returns True if removed."""
    with get_db(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        )
    return cur.rowcount > 0


def update_member_role(db_path: Path, project_id: str, user_id: str, role: str) -> None:
    """Change the role of an existing member."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE project_members SET role = ? WHERE project_id = ? AND user_id = ?",
            (role, project_id, user_id),
        )


def get_member_role(db_path: Path, project_id: str, user_id: str) -> str | None:
    """Return the role of user_id in project_id, or None if not a member."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
    return row["role"] if row else None


def update_project(
    db_path: Path,
    project_id: str,
    name: str | None = None,
    description: str | None = None,
    archived_at: str | None = None,
) -> Project:
    """Update project fields. Omitted fields are unchanged."""
    project = get_project(db_path, project_id)
    if project is None:
        raise ValueError(f"Project {project_id!r} not found")
    new_name = name if name is not None else project.name
    new_desc = description if description is not None else project.description
    new_archived = archived_at if archived_at is not None else project.archived_at
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE projects SET name = ?, description = ?, archived_at = ? WHERE id = ?",
            (new_name, new_desc, new_archived, project_id),
        )
    project.name = new_name
    project.description = new_desc
    project.archived_at = new_archived
    return project


def delete_project(db_path: Path, project_id: str) -> bool:
    """Delete a project and cascade to members/tasks. Returns True if deleted."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return cur.rowcount > 0


def _row_to_project(row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        archived_at=row["archived_at"],
        lab_id=row["lab_id"],
    )
