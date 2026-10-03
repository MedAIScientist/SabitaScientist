"""Export request endpoints — request, review (PI + Privacy Officer), enforce no-download on sensitive data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...crud.exports import (
    create_export_request,
    get_export_request,
    list_export_requests,
    review_export_request,
)
from ...crud.projects import get_project
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_admin, require_project_role
from ..schemas import ExportRequestCreate, ExportRequestResponse, ExportRequestReview

router = APIRouter()


@router.post(
    "/projects/{project_id}/export-requests",
    response_model=ExportRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_export_endpoint(
    project_id: str,
    body: ExportRequestCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    p = get_project(get_db_path(), project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return create_export_request(
        get_db_path(),
        project_id,
        current_user.id,
        body.file_name,
        body.file_type,
        file_size_bytes=body.file_size_bytes,
        description=body.description,
        justification=body.justification,
    )


@router.get(
    "/projects/{project_id}/export-requests", response_model=list[ExportRequestResponse]
)
def list_exports_endpoint(
    project_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    return list_export_requests(
        get_db_path(), project_id=project_id, status=status_filter
    )


@router.get(
    "/projects/{project_id}/export-requests/{export_id}",
    response_model=ExportRequestResponse,
)
def get_export_endpoint(
    project_id: str,
    export_id: str,
    current_user: User = Depends(get_current_user),
):
    e = get_export_request(get_db_path(), export_id)
    if not e or e.project_id != project_id:
        raise HTTPException(404, "Export request not found")
    return e


@router.post(
    "/projects/{project_id}/export-requests/{export_id}/review",
    response_model=ExportRequestResponse,
)
def review_export_endpoint(
    project_id: str,
    export_id: str,
    body: ExportRequestReview,
    current_user: User = Depends(require_project_role("owner")),
):
    e = get_export_request(get_db_path(), export_id)
    if not e or e.project_id != project_id:
        raise HTTPException(404, "Export request not found")
    if e.status != "pending":
        raise HTTPException(400, "Export request already reviewed")
    return review_export_request(
        get_db_path(),
        export_id,
        current_user.id,
        body.status,
        body.reviewer_notes,
    )


# ── Attachment Classification & Download Enforcement ─────────────────────

_BLOCKED_CLASSIFICATIONS = frozenset({"raw_phi"})


def assert_attachment_download_allowed(classification: str) -> None:
    """Raise 403 if the attachment classification blocks download."""
    if classification in _BLOCKED_CLASSIFICATIONS:
        raise HTTPException(
            status_code=403,
            detail="Downloads blocked for this classification. "
            "Submit an export request for approval.",
        )


@router.get("/exports/pending-count")
def pending_exports_count(
    current_user: User = Depends(require_admin),
):
    """Admin endpoint: count all pending export requests."""
    pending = list_export_requests(get_db_path(), status="pending")
    return {"pending_count": len(pending)}
