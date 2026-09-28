"""CVAT annotation project integration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...crud.cvat import (
    create_cvat_project,
    delete_cvat_project,
    get_cvat_project,
    list_cvat_projects,
    update_cvat_project,
)
from ...crud.projects import get_project
from ...db import get_db_path
from ...models import User
from ..deps import require_project_role

router = APIRouter()


class CVATProjectCreate(BaseModel):
    cvat_id: int
    name: str = Field(min_length=1)
    labels_json: str = "[]"


class CVATProjectUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(created|importing|annotating|reviewing|exported|completed)$")
    num_images: int | None = None
    num_annotations: int | None = None
    export_format: str | None = None
    export_key: str | None = None


@router.post("/projects/{project_id}/cvat", status_code=status.HTTP_201_CREATED)
def create_cvat(
    project_id: str,
    body: CVATProjectCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    p = get_project(get_db_path(), project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    cp = create_cvat_project(get_db_path(), project_id, body.cvat_id, body.name, current_user.id, body.labels_json)
    return {"id": cp.id, "name": cp.name, "cvat_id": cp.cvat_id, "status": cp.status}


@router.get("/projects/{project_id}/cvat")
def list_cvat(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    return list_cvat_projects(get_db_path(), project_id)


@router.put("/projects/{project_id}/cvat/{cvat_id}")
def update_cvat(
    project_id: str,
    cvat_id: str,
    body: CVATProjectUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    cp = get_cvat_project(get_db_path(), cvat_id)
    if not cp or cp.project_id != project_id:
        raise HTTPException(404, "CVAT project not found")
    updated = update_cvat_project(
        get_db_path(), cvat_id,
        status=body.status, num_images=body.num_images,
        num_annotations=body.num_annotations,
        export_format=body.export_format, export_key=body.export_key,
    )
    return {"id": updated.id, "status": updated.status, "num_annotations": updated.num_annotations}


@router.delete("/projects/{project_id}/cvat/{cvat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cvat(
    project_id: str,
    cvat_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    cp = get_cvat_project(get_db_path(), cvat_id)
    if not cp or cp.project_id != project_id:
        raise HTTPException(404, "CVAT project not found")
    delete_cvat_project(get_db_path(), cvat_id)
