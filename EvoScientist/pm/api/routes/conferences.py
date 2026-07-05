from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...crud.conferences import (
    create_conference,
    delete_conference,
    get_conference,
    list_conferences,
    update_conference,
)
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
            "id": c.id,
            "name": c.name,
            "venue": c.venue,
            "deadline": c.deadline,
            "status": c.status,
            "presentation_type": c.presentation_type,
            "decision_date": c.decision_date,
        }
        for c in list_conferences(get_db_path(), project_id, status, offset, limit)
    ]


@router.post("", status_code=201)
def create_new(body: dict, current_user: User = Depends(get_current_user)):
    c = create_conference(get_db_path(), created_by=current_user.id, **body)
    return {"id": c.id, "name": c.name, "status": c.status}


@router.get("/{cid}")
def get_detail(cid: str, current_user: User = Depends(get_current_user)):
    c = get_conference(get_db_path(), cid)
    if not c:
        raise HTTPException(404)
    return {
        "id": c.id,
        "name": c.name,
        "venue": c.venue,
        "location": c.location,
        "deadline": c.deadline,
        "submission_date": c.submission_date,
        "decision_date": c.decision_date,
        "status": c.status,
        "presentation_type": c.presentation_type,
        "travel_funding": c.travel_funding,
        "travel_notes": c.travel_notes,
        "url": c.url,
        "notes": c.notes,
        "project_id": c.project_id,
        "publication_id": c.publication_id,
    }


@router.put("/{cid}")
def update_existing(
    cid: str, body: dict, current_user: User = Depends(get_current_user)
):
    c = update_conference(get_db_path(), cid, **body)
    if not c:
        raise HTTPException(404)
    return {"id": c.id, "name": c.name, "status": c.status}


@router.delete("/{cid}", status_code=204)
def delete_existing(cid: str, current_user: User = Depends(get_current_user)):
    delete_conference(get_db_path(), cid)
