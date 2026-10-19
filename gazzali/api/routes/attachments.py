"""Attachment upload/download endpoints.

A file belongs to exactly one owner: an experiment entry or a project task. Upload
validation, presigning, classification and deletion are shared, so a task attachment
behaves like an entry attachment in every way that matters.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import RedirectResponse, StreamingResponse

from ...crud.attachments import (
    create_attachment,
    delete_attachment,
    get_attachment,
    list_attachments,
    list_project_attachments,
    list_task_attachments,
    owner_project_id,
    update_attachment_classification,
)
from ...crud.experiment_entries import get_entry
from ...crud.experiment_metrics import create_metrics, delete_metrics_for_attachment
from ...crud.experiments import get_experiment
from ...crud.projects import get_member_role
from ...crud.tasks import get_task
from ...db import get_db, get_db_path
from ...metrics_csv import is_parseable, parse_metrics_csv
from ...models import User
from ...settings import get_max_upload_bytes
from ...storage import (
    delete_object,
    generate_presigned_url,
    get_object_stream,
    upload_file,
)
from ..deps import get_current_user, require_project_role
from ..schemas import (
    AttachmentClassifyRequest,
    AttachmentResponse,
    ProjectAttachmentResponse,
)

router = APIRouter()
global_router = APIRouter()

_MAX_BYTES = get_max_upload_bytes()

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


async def _read_upload(file: UploadFile) -> tuple[bytes, str, str]:
    """Validate an uploaded file once for every owner it can be attached to."""
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
    return data, file.filename or "upload", content_type


async def _store(content_id: str, folder: str, data: bytes, filename: str, content_type: str) -> str:
    """Put the bytes in object storage under a unique key and return that key."""
    key = f"{folder}/{content_id}/{uuid.uuid4()}/{filename}"
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: upload_file(BytesIO(data), key, content_type))
    return key


def _check_task(project_id: str, task_id: str):
    """Validate the task exists and belongs to the project."""
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _check_entry(project_id: str, exp_id: str, entry_id: str):
    """Validate experiment and entry exist and belong to the project."""
    exp = get_experiment(get_db_path(), exp_id)
    if not exp or exp.project_id != project_id:
        raise HTTPException(status_code=404, detail="Experiment not found")
    entry = get_entry(get_db_path(), entry_id)
    if not entry or entry.experiment_id != exp_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


def _to_response(a, metrics_parsed: int = 0) -> AttachmentResponse:
    return AttachmentResponse(
        metrics_parsed=metrics_parsed,
        id=a.id,
        entry_id=a.entry_id,
        task_id=a.task_id,
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
    data, filename, content_type = await _read_upload(file)
    key = await _store(entry_id, "entries", data, filename, content_type)

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

    metrics_parsed = _extract_metrics(data, filename, content_type, exp_id, attachment.id, current_user.id)
    return _to_response(attachment, metrics_parsed)


def _extract_metrics(
    data: bytes,
    filename: str,
    content_type: str,
    exp_id: str,
    attachment_id: str,
    user_id: str,
) -> int:
    """Record metrics from a results table upload. Returns how many were stored.

    A file that will not decode or parse simply yields zero metrics — the upload
    still succeeds, and the drafting context reports that no numbers exist rather
    than guessing at them.
    """
    if not is_parseable(filename, content_type):
        return 0
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return 0
    metrics = parse_metrics_csv(text)
    if not metrics:
        return 0
    create_metrics(
        get_db_path(),
        experiment_id=exp_id,
        metrics=metrics,
        recorded_by=user_id,
        source_attachment_id=attachment_id,
    )
    return len(metrics)


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


@router.get(
    "/{project_id}/attachments",
    response_model=list[ProjectAttachmentResponse],
    summary="Every file in the project, with the task or entry it belongs to",
)
def list_project_files(
    project_id: str,
    kind: str | None = Query(default=None, pattern="^(task|entry)$"),
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """One place to find a file without opening every task and experiment."""
    with get_db() as db:
        rows = list_project_attachments(db, project_id, kind)
    return [ProjectAttachmentResponse(**row) for row in rows]


@router.post(
    "/{project_id}/tasks/{task_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file attachment to a task",
)
async def upload_task_attachment(
    project_id: str,
    task_id: str,
    file: UploadFile,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Attach a file to a task, so the work has its inputs and outputs next to it."""
    _check_task(project_id, task_id)
    data, filename, content_type = await _read_upload(file)
    key = await _store(task_id, "tasks", data, filename, content_type)

    with get_db() as db:
        attachment = create_attachment(
            db,
            entry_id=None,
            task_id=task_id,
            filename=filename,
            s3_key=key,
            content_type=content_type,
            size_bytes=len(data),
            user_id=current_user.id,
        )
    return _to_response(attachment)


@router.get(
    "/{project_id}/tasks/{task_id}/attachments",
    response_model=list[AttachmentResponse],
    summary="List attachments for a task",
)
def list_attachments_for_task(
    project_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List every file attached to a task."""
    _check_task(project_id, task_id)
    with get_db() as db:
        attachments = list_task_attachments(db, task_id)
    return [_to_response(a) for a in attachments]


_BLOCKED_CLASSIFICATIONS = frozenset({"raw_phi"})


@global_router.get(
    "/attachments/{attachment_id}/download",
    summary="Redirect to presigned S3 download URL",
    status_code=status.HTTP_302_FOUND,
)
def download_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return a 302 redirect to a presigned download URL.

    Attachments classified as ``raw_phi`` cannot be downloaded directly.
    Submit an export request instead.
    """
    with get_db() as db:
        attachment = get_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    _require_file_access(attachment, current_user, "owner", "editor", "viewer")
    _blocked_if_phi(attachment)
    url = generate_presigned_url(attachment.s3_key)
    return RedirectResponse(url=url, status_code=302)


def _require_file_access(attachment, user: User, *roles: str) -> None:
    """Authorise an action on a file through the project that owns it.

    These endpoints take only an attachment id, so the project has to be resolved
    from the owning row. Without this, any signed-in account could delete or
    reclassify another project's file just by knowing its id.
    """
    with get_db() as db:
        project_id = owner_project_id(db, attachment.id)
    if project_id is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    role = get_member_role(get_db_path(), project_id, user.id)
    if role is None:
        # Same as "not found": a non-member should not learn that the file exists.
        raise HTTPException(status_code=404, detail="Attachment not found")
    if role not in roles:
        raise HTTPException(
            status_code=403, detail=f"Role '{role}' is not permitted here"
        )


def _blocked_if_phi(attachment) -> None:
    if attachment.classification in _BLOCKED_CLASSIFICATIONS:
        raise HTTPException(
            status_code=403,
            detail="This file contains protected patient data and cannot be "
            "downloaded. Submit an export request through the project's "
            "export-requests endpoint for approval.",
        )


@global_router.get(
    "/attachments/{attachment_id}/content",
    summary="Serve an attachment's bytes through the API",
)
def download_attachment_content(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return the file itself, authenticated, from this origin.

    The response also carries a presigned URL, but in this deployment the object
    store is only reachable inside the compose network, so a browser cannot follow
    one. Serving the bytes here keeps viewing and downloading working behind the
    existing nginx, without exposing the bucket, and keeps the PHI rule in force.
    """
    with get_db() as db:
        attachment = get_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    _require_file_access(attachment, current_user, "owner", "editor", "viewer")
    _blocked_if_phi(attachment)

    buf = get_object_stream(attachment.s3_key)
    # A filename is user input and lands in a header: strip anything that could
    # break out of it, and send the real name RFC 5987 style.
    fallback = re.sub(r'[^A-Za-z0-9._ -]', "_", attachment.filename)[:120] or "download"
    quoted = quote(attachment.filename, safe="")
    return StreamingResponse(
        buf,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": (
                f'inline; filename="{fallback}"; filename*=UTF-8\'\'{quoted}'
            ),
            "Content-Length": str(attachment.size_bytes),
        },
    )


@global_router.put(
    "/attachments/{attachment_id}/classify",
    response_model=AttachmentResponse,
    summary="Set data classification on an attachment",
)
def classify_attachment(
    attachment_id: str,
    body: AttachmentClassifyRequest,
    current_user: User = Depends(get_current_user),
):
    """Update the data classification label on an attachment.

    Values: ``unclassified``, ``raw_phi``, ``de_identified``,
    ``aggregate``, ``model_weights``, ``public``.
    """
    with get_db() as db:
        attachment = get_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    _require_file_access(attachment, current_user, "owner", "editor")
    with get_db() as db:
        updated = update_attachment_classification(
            db, attachment_id, body.classification
        )
    return _to_response(updated)


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
    _require_file_access(attachment, current_user, "owner", "editor")
    delete_object(attachment.s3_key)
    # Metrics must not outlive the file they were read from, or a paper could
    # cite numbers whose source no longer exists.
    delete_metrics_for_attachment(get_db_path(), attachment_id)
    with get_db() as db:
        delete_attachment(db, attachment_id)
