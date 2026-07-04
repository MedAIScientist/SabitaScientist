"""Project and member management routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...crud.projects import (
    add_member,
    create_project,
    delete_project,
    get_project,
    list_projects_for_user,
    remove_member,
    update_member_role,
    update_project,
)
from ...crud.users import get_user_by_id
from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import (
    AddMemberRequest,
    MemberResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    UpdateMemberRoleRequest,
)

router = APIRouter()


def _project_to_response(project, db_path) -> ProjectResponse:
    """Build a ProjectResponse including member list."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT pm.user_id, pm.role, pm.added_at, u.username
               FROM project_members pm JOIN users u ON pm.user_id = u.id
               WHERE pm.project_id = ?""",
            (project.id,),
        ).fetchall()
    members = [
        MemberResponse(
            user_id=r["user_id"],
            username=r["username"],
            role=r["role"],
            added_at=r["added_at"],
        )
        for r in rows
    ]
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_by=project.created_by,
        created_at=project.created_at,
        archived_at=project.archived_at,
        lab_id=project.lab_id,
        members=members,
    )


@router.get("", response_model=list[ProjectResponse])
def list_my_projects(
    current_user: User = Depends(get_current_user),
    lab_id: str | None = Query(default=None),
):
    """List projects the current user is a member of. Optionally filter by lab_id."""
    db = get_db_path()
    return [
        _project_to_response(p, db)
        for p in list_projects_for_user(db, current_user.id, lab_id=lab_id)
    ]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_new_project(
    body: ProjectCreate, current_user: User = Depends(get_current_user)
):
    """Create a new project (creator becomes owner)."""
    db = get_db_path()
    project = create_project(
        db, name=body.name, description=body.description, created_by=current_user.id, lab_id=body.lab_id
    )
    return _project_to_response(project, db)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_detail(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """Get project detail (members only)."""
    db = get_db_path()
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(project, db)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_existing_project(
    project_id: str,
    body: ProjectUpdate,
    current_user: User = Depends(require_project_role("owner")),
):
    """Update project name/description/archive (owner only)."""
    db = get_db_path()
    archived_at = datetime.now(UTC).isoformat() if body.archive else None
    project = update_project(
        db,
        project_id,
        name=body.name,
        description=body.description,
        archived_at=archived_at,
    )
    return _project_to_response(project, db)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_project(
    project_id: str,
    current_user: User = Depends(require_project_role("owner")),
):
    """Delete a project (owner only)."""
    delete_project(get_db_path(), project_id)


@router.post(
    "/{project_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_project_member(
    project_id: str,
    body: AddMemberRequest,
    current_user: User = Depends(require_project_role("owner")),
):
    """Add a member to the project (owner only)."""
    db = get_db_path()
    user = get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    member = add_member(db, project_id=project_id, user_id=body.user_id, role=body.role)
    return MemberResponse(
        user_id=member.user_id,
        username=user.username,
        role=member.role,
        added_at=member.added_at,
    )


@router.put("/{project_id}/members/{user_id}", response_model=MemberResponse)
def change_member_role(
    project_id: str,
    user_id: str,
    body: UpdateMemberRoleRequest,
    current_user: User = Depends(require_project_role("owner")),
):
    """Change a member's role (owner only)."""
    db = get_db_path()
    update_member_role(db, project_id=project_id, user_id=user_id, role=body.role)
    user = get_user_by_id(db, user_id)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT added_at FROM project_members WHERE project_id=? AND user_id=?",
            (project_id, user_id),
        ).fetchone()
    return MemberResponse(
        user_id=user_id,
        username=user.username if user else user_id,
        role=body.role,
        added_at=row["added_at"],
    )


@router.delete(
    "/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_project_member(
    project_id: str,
    user_id: str,
    current_user: User = Depends(require_project_role("owner")),
):
    """Remove a member from the project (owner only)."""
    remove_member(get_db_path(), project_id=project_id, user_id=user_id)
