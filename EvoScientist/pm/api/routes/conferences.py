"""Conference management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ...crud.conferences import (
    create_conference,
    delete_conference,
    get_conference,
    list_conferences,
    update_conference,
)
from ...db import get_db_path
from ...models import User
from ..audit_helper import log_action
from ..deps import get_current_user
from ..schemas import ConferenceCreate, ConferenceResponse, ConferenceUpdate

router = APIRouter()


@router.get("", response_model=list[ConferenceResponse])
def list_all(
    current_user: User = Depends(get_current_user),
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_db_path()
    return [
        ConferenceResponse(
            id=c.id,
            name=c.name,
            venue=c.venue,
            location=c.location,
            deadline=c.deadline,
            submission_date=c.submission_date,
            decision_date=c.decision_date,
            status=c.status,
            presentation_type=c.presentation_type,
            travel_funding=c.travel_funding,
            travel_notes=c.travel_notes,
            url=c.url,
            notes=c.notes,
            project_id=c.project_id,
            publication_id=c.publication_id,
            created_by=c.created_by,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in list_conferences(db, project_id, status, offset, limit)
    ]


@router.post("", response_model=ConferenceResponse, status_code=status.HTTP_201_CREATED)
def create_new(
    request: Request,
    body: ConferenceCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    c = create_conference(
        db,
        name=body.name,
        created_by=current_user.id,
        project_id=body.project_id,
        publication_id=body.publication_id,
        venue=body.venue,
        location=body.location,
        deadline=body.deadline,
        submission_date=body.submission_date,
        decision_date=body.decision_date,
        status=body.status,
        presentation_type=body.presentation_type,
        travel_funding=body.travel_funding,
        travel_notes=body.travel_notes,
        url=body.url,
        notes=body.notes,
    )
    log_action(request, current_user, "create", "conference", c.id, f"name={c.name}")
    return ConferenceResponse(
        id=c.id,
        name=c.name,
        venue=c.venue,
        location=c.location,
        deadline=c.deadline,
        submission_date=c.submission_date,
        decision_date=c.decision_date,
        status=c.status,
        presentation_type=c.presentation_type,
        travel_funding=c.travel_funding,
        travel_notes=c.travel_notes,
        url=c.url,
        notes=c.notes,
        project_id=c.project_id,
        publication_id=c.publication_id,
        created_by=c.created_by,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/{cid}", response_model=ConferenceResponse)
def get_detail(
    cid: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    c = get_conference(db, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Conference not found")
    return ConferenceResponse(
        id=c.id,
        name=c.name,
        venue=c.venue,
        location=c.location,
        deadline=c.deadline,
        submission_date=c.submission_date,
        decision_date=c.decision_date,
        status=c.status,
        presentation_type=c.presentation_type,
        travel_funding=c.travel_funding,
        travel_notes=c.travel_notes,
        url=c.url,
        notes=c.notes,
        project_id=c.project_id,
        publication_id=c.publication_id,
        created_by=c.created_by,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.put("/{cid}", response_model=ConferenceResponse)
def update_existing(
    request: Request,
    cid: str,
    body: ConferenceUpdate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    c = update_conference(
        db,
        cid,
        name=body.name,
        venue=body.venue,
        location=body.location,
        deadline=body.deadline,
        submission_date=body.submission_date,
        decision_date=body.decision_date,
        status=body.status,
        presentation_type=body.presentation_type,
        travel_funding=body.travel_funding,
        travel_notes=body.travel_notes,
        url=body.url,
        notes=body.notes,
        project_id=body.project_id,
        publication_id=body.publication_id,
    )
    if not c:
        raise HTTPException(status_code=404, detail="Conference not found")
    log_action(request, current_user, "update", "conference", cid, f"name={c.name}")
    return ConferenceResponse(
        id=c.id,
        name=c.name,
        venue=c.venue,
        location=c.location,
        deadline=c.deadline,
        submission_date=c.submission_date,
        decision_date=c.decision_date,
        status=c.status,
        presentation_type=c.presentation_type,
        travel_funding=c.travel_funding,
        travel_notes=c.travel_notes,
        url=c.url,
        notes=c.notes,
        project_id=c.project_id,
        publication_id=c.publication_id,
        created_by=c.created_by,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.delete("/{cid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing(
    request: Request,
    cid: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    c = get_conference(db, cid)
    if c:
        log_action(request, current_user, "delete", "conference", cid, f"name={c.name}")
    delete_conference(db, cid)
