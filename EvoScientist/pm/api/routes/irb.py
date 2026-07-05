from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...crud.irb import create_irb, delete_irb, get_irb, list_irbs, update_irb
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user

router = APIRouter()


@router.get("")
def list_all(
    current_user: User = Depends(get_current_user),
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return [
        {
            "id": i.id,
            "title": i.title,
            "institution": i.institution,
            "protocol_number": i.protocol_number,
            "status": i.status,
            "approval_date": i.approval_date,
            "expiry_date": i.expiry_date,
        }
        for i in list_irbs(get_db_path(), project_id, status, offset, limit)
    ]


@router.post("", status_code=201)
def create_new(body: dict, current_user: User = Depends(get_current_user)):
    i = create_irb(get_db_path(), created_by=current_user.id, **body)
    return {"id": i.id, "title": i.title, "status": i.status}


@router.get("/{iid}")
def get_detail(iid: str, current_user: User = Depends(get_current_user)):
    i = get_irb(get_db_path(), iid)
    if not i:
        raise HTTPException(404)
    return {
        "id": i.id,
        "project_id": i.project_id,
        "institution": i.institution,
        "protocol_number": i.protocol_number,
        "title": i.title,
        "status": i.status,
        "approval_date": i.approval_date,
        "expiry_date": i.expiry_date,
        "renewal_date": i.renewal_date,
        "documents": i.documents,
        "notes": i.notes,
    }


@router.put("/{iid}")
def update_existing(
    iid: str, body: dict, current_user: User = Depends(get_current_user)
):
    i = update_irb(get_db_path(), iid, **body)
    if not i:
        raise HTTPException(404)
    return {"id": i.id, "title": i.title, "status": i.status}


@router.delete("/{iid}", status_code=204)
def delete_existing(iid: str, current_user: User = Depends(get_current_user)):
    delete_irb(get_db_path(), iid)
