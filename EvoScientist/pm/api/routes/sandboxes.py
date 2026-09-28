"""Sandbox endpoints — provision, manage lifecycle, link to IRB for auto-expiry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.irb import get_irb
from ...crud.projects import get_project
from ...crud.sandboxes import (
    create_sandbox,
    delete_sandbox,
    get_sandbox,
    list_sandboxes,
    update_sandbox,
)
from ...db import get_db_path
from ...models import User
from ..deps import require_project_role
from ..schemas import SandboxCreate, SandboxResponse, SandboxUpdate

router = APIRouter()


@router.post(
    "/projects/{project_id}/sandboxes",
    response_model=SandboxResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_sandbox_endpoint(
    project_id: str,
    body: SandboxCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    p = get_project(get_db_path(), project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    if body.irb_id:
        irb = get_irb(get_db_path(), body.irb_id)
        if not irb or irb.project_id != project_id:
            raise HTTPException(400, "IRB not found or not in this project")
    return create_sandbox(
        get_db_path(),
        project_id,
        body.name,
        current_user.id,
        spec_json=body.spec_json,
        network_rules_json=body.network_rules_json,
        irb_id=body.irb_id,
        storage_quota_bytes=body.storage_quota_bytes,
        expires_at=body.expires_at,
    )


@router.get("/projects/{project_id}/sandboxes", response_model=list[SandboxResponse])
def list_sandboxes_endpoint(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    return list_sandboxes(get_db_path(), project_id)


@router.get(
    "/projects/{project_id}/sandboxes/{sandbox_id}", response_model=SandboxResponse
)
def get_sandbox_endpoint(
    project_id: str,
    sandbox_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    s = get_sandbox(get_db_path(), sandbox_id)
    if not s or s.project_id != project_id:
        raise HTTPException(404, "Sandbox not found")
    return s


@router.put(
    "/projects/{project_id}/sandboxes/{sandbox_id}", response_model=SandboxResponse
)
def update_sandbox_endpoint(
    project_id: str,
    sandbox_id: str,
    body: SandboxUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    s = get_sandbox(get_db_path(), sandbox_id)
    if not s or s.project_id != project_id:
        raise HTTPException(404, "Sandbox not found")
    return update_sandbox(
        get_db_path(),
        sandbox_id,
        status=body.status,
        access_url=body.access_url,
        spec_json=body.spec_json,
        expires_at=body.expires_at,
    )


@router.delete(
    "/projects/{project_id}/sandboxes/{sandbox_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_sandbox_endpoint(
    project_id: str,
    sandbox_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    s = get_sandbox(get_db_path(), sandbox_id)
    if not s or s.project_id != project_id:
        raise HTTPException(404, "Sandbox not found")
    delete_sandbox(get_db_path(), sandbox_id)
