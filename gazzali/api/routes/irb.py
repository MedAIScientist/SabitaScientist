"""IRB approval management routes.

LOCKED DOWN (20 Aug 2026): an IRB row is the precondition for releasing PHI
cohorts, so it can no longer be self-service. The rules, in one place:

* CREATE — needs write on the referenced project (project owner/editor, the
  project's lab PI/admin, or a platform admin). Born ``draft`` or ``submitted``
  only; a row can never be created already 'approved'.
* DECIDE — only a platform admin can set ``approved`` or ``rejected``, and only
  from ``submitted``. Approval requires an approval_date, a future expiry_date
  and at least one document reference, and records WHO approved (approved_by).
* APPROVED ROWS ARE IMMUTABLE — the only edits allowed afterwards are an admin
  transitioning to ``expired`` or ``closed``. Protocol fields are frozen.
* DELETE — never. IRB records are append-only; close them instead. (The old
  DELETE endpoint remains but answers 403 for everyone, admins included.)
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ...crud.irb import create_irb, get_irb, list_irbs, update_irb
from ...crud.labs import get_member_role as get_lab_member_role
from ...crud.projects import get_member_role as get_project_member_role
from ...crud.projects import get_project
from ...db import get_db_path
from ...models import IRBApproval, User
from ..audit_helper import log_action
from ..deps import get_current_user
from ..schemas import IRBCreate, IRBResponse, IRBUpdate

router = APIRouter()

_PROJECT_WRITE_ROLES = {"owner", "editor"}
_LAB_WRITE_ROLES = {"pi", "admin"}
_DECISION_STATUSES = {"approved", "rejected"}
_ADMIN_LIFECYCLE = {"expired", "closed"}


def _may_write_irb(db, user: User, project_id: str) -> bool:
    """Write = platform admin, project owner/editor, or the project's lab PI/admin
    — the same shape as the grants write check."""
    if user.is_admin:
        return True
    if get_project_member_role(db, project_id, user.id) in _PROJECT_WRITE_ROLES:
        return True
    project = get_project(db, project_id)
    if (
        project
        and project.lab_id
        and get_lab_member_role(db, project.lab_id, user.id) in _LAB_WRITE_ROLES
    ):
        return True
    return False


def _resp(i: IRBApproval) -> IRBResponse:
    return IRBResponse(
        id=i.id,
        project_id=i.project_id,
        institution=i.institution,
        protocol_number=i.protocol_number,
        title=i.title,
        status=i.status,
        approval_date=i.approval_date,
        expiry_date=i.expiry_date,
        renewal_date=i.renewal_date,
        documents=i.documents or [],
        notes=i.notes,
        created_by=i.created_by,
        created_at=i.created_at,
        updated_at=i.updated_at,
        approved_by=i.approved_by,
        approved_at=i.approved_at,
    )


@router.get("", response_model=list[IRBResponse])
def list_all(
    current_user: User = Depends(get_current_user),
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_db_path()
    return [_resp(i) for i in list_irbs(db, project_id, status, offset, limit)]


@router.post("", response_model=IRBResponse, status_code=status.HTTP_201_CREATED)
def create_new(
    request: Request,
    body: IRBCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    if not get_project(db, body.project_id):
        raise HTTPException(status_code=400, detail="project does not exist")
    if not _may_write_irb(db, current_user, body.project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IRB records require write on the referenced project "
            "(project owner/editor or the lab's pi/admin)",
        )
    i = create_irb(
        db,
        project_id=body.project_id,
        institution=body.institution,
        protocol_number=body.protocol_number,
        title=body.title,
        created_by=current_user.id,
        status=body.status,  # schema restricts this to draft|submitted
        approval_date=body.approval_date,
        expiry_date=body.expiry_date,
        renewal_date=body.renewal_date,
        documents=body.documents,
        notes=body.notes,
    )
    log_action(request, current_user, "create", "irb", i.id, f"title={i.title}")
    return _resp(i)


@router.get("/{iid}", response_model=IRBResponse)
def get_detail(
    iid: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    i = get_irb(db, iid)
    if not i:
        raise HTTPException(status_code=404, detail="IRB approval not found")
    return _resp(i)


@router.put("/{iid}", response_model=IRBResponse)
def update_existing(
    request: Request,
    iid: str,
    body: IRBUpdate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    i = get_irb(db, iid)
    if not i:
        raise HTTPException(status_code=404, detail="IRB approval not found")

    non_status_edits = any(
        v is not None
        for v in (
            body.approval_date,
            body.expiry_date,
            body.renewal_date,
            body.documents,
            body.notes,
            body.institution,
            body.protocol_number,
        )
    )

    # An approved IRB is a sealed record: admins may expire/close it, nothing else.
    if i.status == "approved":
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="approved IRB records are immutable",
            )
        if body.status not in _ADMIN_LIFECYCLE or non_status_edits:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="an approved IRB can only be transitioned to expired or closed",
            )
        i = update_irb(db, iid, status=body.status)
        log_action(request, current_user, body.status, "irb", iid, f"title={i.title}")
        return _resp(i)

    if not _may_write_irb(db, current_user, i.project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IRB records require write on the referenced project "
            "(project owner/editor or the lab's pi/admin)",
        )

    approved_by = None
    approved_at = None
    if body.status in _DECISION_STATUSES:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="only a platform admin can decide an IRB "
                "(approved/rejected)",
            )
        if i.status != "submitted":
            raise HTTPException(
                status_code=409,
                detail=f"only a submitted IRB can be decided (is: {i.status})",
            )
        if body.status == "approved":
            eff_approval = body.approval_date or i.approval_date
            eff_expiry = body.expiry_date or i.expiry_date
            eff_docs = body.documents if body.documents is not None else i.documents
            today = datetime.now(UTC).date().isoformat()
            if not eff_approval:
                raise HTTPException(
                    status_code=409, detail="approval requires an approval_date"
                )
            if not eff_expiry or eff_expiry <= today:
                raise HTTPException(
                    status_code=409, detail="approval requires a future expiry_date"
                )
            if not eff_docs:
                raise HTTPException(
                    status_code=409,
                    detail="approval requires at least one document reference",
                )
            approved_by = current_user.id
            approved_at = datetime.now(UTC).isoformat()
    elif body.status == "expired":
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="only a platform admin can expire an IRB",
            )

    i = update_irb(
        db,
        iid,
        status=body.status,
        approval_date=body.approval_date,
        expiry_date=body.expiry_date,
        renewal_date=body.renewal_date,
        documents=body.documents,
        notes=body.notes,
        institution=body.institution,
        protocol_number=body.protocol_number,
        approved_by=approved_by,
        approved_at=approved_at,
    )
    log_action(request, current_user, "update", "irb", iid, f"title={i.title}")
    return _resp(i)


@router.delete("/{iid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing(
    request: Request,
    iid: str,
    current_user: User = Depends(get_current_user),
):
    """Gone on purpose: an IRB row is the audit anchor for PHI releases, so it is
    append-only for everyone — platform admins included. Close it instead."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="IRB records are append-only; set status='closed' instead of deleting",
    )
