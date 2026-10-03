"""Data export endpoints — CSV, JSON, and Markdown/PDF for projects, tasks, publications."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ...crud.experiments import list_experiments
from ...crud.projects import get_project, list_projects_for_user
from ...crud.publications import list_publications
from ...crud.tasks import list_tasks
from ...crud.users import list_users
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_admin

router = APIRouter()


@router.get("/export/projects/csv")
def export_projects_csv(current_user: User = Depends(get_current_user)):
    db = get_db_path()
    projects = list_projects_for_user(db, current_user.id)
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["id", "name", "description", "created_by", "created_at", "archived_at", "lab_id"])
    for p in projects:
        w.writerow([p.id, p.name, p.description, p.created_by, p.created_at, p.archived_at, p.lab_id])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=projects.csv"})


@router.get("/export/projects/json")
def export_projects_json(current_user: User = Depends(get_current_user)):
    db = get_db_path()
    projects = list_projects_for_user(db, current_user.id)
    result = []
    for p in projects:
        tasks = list_tasks(db, p.id)
        exps = list_experiments(db, p.id)
        result.append({
            "id": p.id, "name": p.name, "description": p.description,
            "created_at": p.created_at, "archived_at": p.archived_at,
            "task_count": len(tasks),
            "experiment_count": len(exps),
        })
    return result


@router.get("/export/tasks/{project_id}/csv")
def export_tasks_csv(project_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    tasks = list_tasks(db, project_id)
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["id", "title", "status", "priority", "assignee_id", "deadline", "created_at"])
    for t in tasks:
        w.writerow([t.id, t.title, t.status, t.priority, t.assignee_id, t.deadline, t.created_at])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=tasks-{project_id}.csv"})


@router.get("/export/publications/csv")
def export_publications_csv(current_user: User = Depends(get_current_user)):
    db = get_db_path()
    pubs = list_publications(db)
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["id", "title", "status", "venue", "venue_type", "doi", "created_at", "published_at"])
    for p in pubs:
        w.writerow([p.id, p.title, p.status, p.venue, p.venue_type, p.doi, p.created_at, p.published_at])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=publications.csv"})


@router.get("/export/users/csv")
def export_users_csv(current_user: User = Depends(require_admin)):
    db = get_db_path()
    users = list_users(db)
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["id", "username", "email", "is_admin", "created_at"])
    for u in users:
        w.writerow([u.id, u.username, u.email, u.is_admin, u.created_at])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=users.csv"})
