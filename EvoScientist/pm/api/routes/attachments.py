"""Attachment upload/download endpoints for experiment entries."""
from __future__ import annotations

import asyncio
import os
import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse

from ...crud.attachments import (
    create_attachment,
    delete_attachment,
    get_attachment,
    list_attachments,
)
from ...crud.experiment_entries import get_entry
from ...crud.experiments import get_experiment
from ...db import get_db, get_db_path
from ...models import User
from ...storage import delete_object, generate_presigned_url, upload_file
from ..deps import get_current_user, require_project_role
from ..schemas import AttachmentResponse

router = APIRouter()
global_router = APIRouter()

_MAX_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "50")) * 1024 * 1024

_ALLOWED_MIME_PREFIXES = (
    "image/",
    "text/",
    "application/pdf",
    "application/json",
    "application/zip",
    "application/gzip",
    "application/x-tar",
    "application/octet-stream",
)


def _check_entry(project_id: str, exp_id: str, entry_id: str):
    """Validate experiment and entry exist and belong to the project."""
    exp = get_experiment(get_db_path(), exp_id)
    if not exp or exp.project_id != project_id:
        raise HTTPException(status_code=404, detail="Experiment not found")
    entry = get_entry(get_db_path(), entry_id)
    if not entry or entry.experiment_id != exp_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


def _to_response(a) -> AttachmentResponse:
    return AttachmentResponse(
        id=a.id,
        entry_id=a.entry_id,
        filename=a.filename,
        content_type=a.content_type,
        size_bytes=a.size_bytes,
        uploaded_by=a.uploaded_by,
        created_at=a.created_at,
        download_url=generate_presigned_url(a.s3_key),
    )


@router.post(
    "/{project_id}/experiments/{exp_id}/entries/{entry_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file attachment to an experiment entry",
)
async def upload_attachment(
    project_id: str,
    exp_id: str,
    entry_id: str,
    file: UploadFile,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Upload a file to S3 and record its metadata."""
    _check_entry(project_id, exp_id, entry_id)

    content_type = file.content_type or "application/octet-stream"
    if not any(content_type.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{content_type}' is not allowed.",
        )

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {_MAX_BYTES // (1024 * 1024)} MB.",
        )

    filename = file.filename or "upload"
    key = f"entries/{entry_id}/{uuid.uuid4()}/{filename}"

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: upload_file(BytesIO(data), key, content_type))

    with get_db() as db:
        attachment = create_attachment(
            db,
            entry_id=entry_id,
            filename=filename,
            s3_key=key,
            content_type=content_type,
            size_bytes=len(data),
            user_id=current_user.id,
        )

    return _to_response(attachment)


@router.get(
    "/{project_id}/experiments/{exp_id}/entries/{entry_id}/attachments",
    response_model=list[AttachmentResponse],
    summary="List attachments for an experiment entry",
)
def list_entry_attachments(
    project_id: str,
    exp_id: str,
    entry_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List all attachments for an experiment entry."""
    _check_entry(project_id, exp_id, entry_id)
    with get_db() as db:
        attachments = list_attachments(db, entry_id)
    return [_to_response(a) for a in attachments]


@global_router.get(
    "/attachments/{attachment_id}/download",
    summary="Redirect to presigned S3 download URL",
    status_code=status.HTTP_302_FOUND,
)
def download_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return a 302 redirect to a presigned download URL."""
    with get_db() as db:
        attachment = get_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    url = generate_presigned_url(attachment.s3_key)
    return RedirectResponse(url=url, status_code=302)


@global_router.delete(
    "/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an attachment",
)
def delete_attachment_endpoint(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete attachment from S3 and database."""
    with get_db() as db:
        attachment = get_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    delete_object(attachment.s3_key)
    with get_db() as db:
        delete_attachment(db, attachment_id)
