from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.phases import assign_task_phase, create_phase
from ...crud.projects import create_project
from ...crud.tasks import create_task
from ...db import get_db, get_db_path
from ...models import User
from ...templates import get_template, list_templates, template_to_dict
from ..deps import get_current_user
from ..schemas import (
    MemberResponse,
    ProjectFromTemplateRequest,
    ProjectResponse,
    TemplateResponse,
)

router = APIRouter()


@router.get("", response_model=list[TemplateResponse])
def list_available_templates(current_user: User = Depends(get_current_user)):
    return [template_to_dict(t) for t in list_templates()]


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template_detail(
    template_id: str,
    current_user: User = Depends(get_current_user),
):
    t = get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return template_to_dict(t)


@router.post("/from-template", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_from_template(
    body: ProjectFromTemplateRequest,
    current_user: User = Depends(get_current_user),
):
    t = get_template(body.template_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Template {body.template_id!r} not found")

    db = get_db_path()

    project = create_project(
        db,
        name=body.name,
        description=body.description or t.description,
        created_by=current_user.id,
        lab_id=body.lab_id,
    )

    phase_map: dict[str, str] = {}
    for pt in t.phases:
        phase = create_phase(
            db,
            project_id=project.id,
            name=pt.name,
            color=pt.color,
            position=pt.position,
            target_date=None,
            created_by=current_user.id,
        )
        phase_map[pt.name] = phase.id

    for task_t in t.tasks:
        phase_id = phase_map.get(task_t.phase)
        task = create_task(
            db,
            project_id=project.id,
            title=task_t.title,
            created_by=current_user.id,
            description=task_t.description,
            priority=task_t.priority,
        )
        if phase_id and task.id:
            assign_task_phase(db, task.id, phase_id)

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT id, name, description, created_by, created_at, archived_at, lab_id FROM projects WHERE id = ?",
            (project.id,),
        ).fetchone()
        member_rows = conn.execute(
            """SELECT pm.user_id, pm.role, pm.added_at, u.username
               FROM project_members pm JOIN users u ON pm.user_id = u.id
               WHERE pm.project_id = ?""",
            (project.id,),
        ).fetchall()
    members = [
        MemberResponse(user_id=r["user_id"], username=r["username"], role=r["role"], added_at=r["added_at"])
        for r in member_rows
    ]
    return ProjectResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        archived_at=row["archived_at"],
        lab_id=row["lab_id"],
        members=members,
    )
