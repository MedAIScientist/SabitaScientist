"""CVAT provisioning — create a project's CVAT counterpart once, idempotently."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from ...crud.cvat import create_cvat_project, list_cvat_projects
from ...crud.projects import get_project
from ...cvat_client import CVATError, create_project, is_configured
from ...db import get_db_path
from ...models import User
from ..deps import require_project_role

router = APIRouter()


class CVATProvisionRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    labels: list[dict] = []


@router.post("/projects/{project_id}/cvat/provision", status_code=status.HTTP_201_CREATED)
async def provision_cvat(
    project_id: str,
    body: CVATProvisionRequest,
    response: Response,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Create this project's CVAT project, or return the link that already exists.

    201 when a CVAT project was created, 200 when one was already linked.
    """
    db = get_db_path()
    p = get_project(db, project_id)
    if not p:
        raise HTTPException(404, "Project not found")

    # Idempotent by design: never create a second CVAT project for the same PM project.
    # Two simultaneous requests could still both pass this check — there is no unique
    # constraint on (project_id, cvat_id) and adding one is out of scope — so the link
    # is treated as first-writer-wins rather than enforced in the schema.
    existing = list_cvat_projects(db, project_id)
    if existing:
        response.status_code = status.HTTP_200_OK
        return existing[0]

    if not is_configured():
        raise HTTPException(503, "CVAT is not configured")

    name = body.name or p.name
    try:
        remote = await create_project(name, body.labels)
    except CVATError as exc:
        raise HTTPException(502, f"CVAT project creation failed: {exc}") from exc

    cvat_id = remote.get("id")
    if not isinstance(cvat_id, int):
        raise HTTPException(502, "CVAT did not return a project id")

    try:
        create_cvat_project(db, project_id, cvat_id, name, current_user.id, json.dumps(body.labels))
    except Exception as exc:
        # The CVAT project exists but is now unreferenced. Name its id so it can be
        # adopted or deleted by hand instead of quietly leaking.
        raise HTTPException(
            502, f"CVAT project {cvat_id} was created but could not be linked: {exc}"
        ) from exc

    # create_cvat_project() reads the new row back inside its own still-uncommitted
    # transaction, so it returns None even though the insert succeeds. Re-read the
    # committed row rather than trusting that return value.
    linked = list_cvat_projects(db, project_id)
    if not linked:
        raise HTTPException(502, f"CVAT project {cvat_id} was created but could not be linked")
    return linked[0]
