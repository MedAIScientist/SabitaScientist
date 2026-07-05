from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...crud.grants import (
    create_grant,
    delete_grant,
    get_grant,
    list_grants,
    update_grant,
)
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user

router = APIRouter()


@router.get("")
def list_all_grants(
    current_user: User = Depends(get_current_user),
    lab_id: str | None = Query(None),
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return [
        {
            "id": g.id,
            "title": g.title,
            "funder": g.funder,
            "amount_awarded": g.amount_awarded,
            "currency": g.currency,
            "status": g.status,
            "submitted_at": g.submitted_at,
            "start_date": g.start_date,
            "end_date": g.end_date,
            "project_id": g.project_id,
            "lab_id": g.lab_id,
            "created_at": g.created_at,
        }
        for g in list_grants(get_db_path(), lab_id, project_id, status, offset, limit)
    ]


@router.post("", status_code=201)
def create_new_grant(body: dict, current_user: User = Depends(get_current_user)):
    g = create_grant(get_db_path(), created_by=current_user.id, **body)
    return {"id": g.id, "title": g.title, "status": g.status}


@router.get("/{gid}")
def get_grant_detail(gid: str, current_user: User = Depends(get_current_user)):
    g = get_grant(get_db_path(), gid)
    if not g:
        raise HTTPException(404)
    return {
        "id": g.id,
        "title": g.title,
        "funder": g.funder,
        "amount_requested": g.amount_requested,
        "amount_awarded": g.amount_awarded,
        "currency": g.currency,
        "status": g.status,
        "submitted_at": g.submitted_at,
        "awarded_at": g.awarded_at,
        "start_date": g.start_date,
        "end_date": g.end_date,
        "description": g.description,
        "pi_id": g.pi_id,
        "project_id": g.project_id,
        "lab_id": g.lab_id,
        "created_at": g.created_at,
    }


@router.put("/{gid}")
def update_existing_grant(
    gid: str, body: dict, current_user: User = Depends(get_current_user)
):
    g = update_grant(get_db_path(), gid, **body)
    if not g:
        raise HTTPException(404)
    return {"id": g.id, "title": g.title, "status": g.status}


@router.delete("/{gid}", status_code=204)
def delete_existing_grant(gid: str, current_user: User = Depends(get_current_user)):
    delete_grant(get_db_path(), gid)
