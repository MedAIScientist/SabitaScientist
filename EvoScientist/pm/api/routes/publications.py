from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...crud.publications import (
    create_publication,
    create_review,
    create_version,
    delete_publication,
    get_publication,
    list_publications,
    list_reviews,
    list_versions,
    update_publication,
)
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user
from ..schemas import (
    PublicationCreate,
    PublicationResponse,
    PublicationUpdate,
    ReviewCreate,
    ReviewResponse,
    VersionCreate,
    VersionResponse,
)

router = APIRouter()


def _pub_to_response(pub) -> PublicationResponse:
    return PublicationResponse(
        id=pub.id,
        project_id=pub.project_id,
        title=pub.title,
        venue=pub.venue,
        venue_type=pub.venue_type,
        authors=pub.authors,
        status=pub.status,
        doi=pub.doi,
        url=pub.url,
        abstract=pub.abstract,
        submitted_at=pub.submitted_at,
        accepted_at=pub.accepted_at,
        published_at=pub.published_at,
        created_by=pub.created_by,
        created_at=pub.created_at,
        updated_at=pub.updated_at,
    )


@router.get("", response_model=list[PublicationResponse])
def list_all_publications(
    current_user: User = Depends(get_current_user),
    project_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    db = get_db_path()
    return [_pub_to_response(p) for p in list_publications(db, project_id=project_id, status=status)]


@router.post("", response_model=PublicationResponse, status_code=status.HTTP_201_CREATED)
def create_new_publication(
    body: PublicationCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    pub = create_publication(
        db,
        title=body.title,
        created_by=current_user.id,
        project_id=body.project_id,
        venue=body.venue,
        venue_type=body.venue_type,
        authors=body.authors,
        abstract=body.abstract,
        doi=body.doi,
        url=body.url,
    )
    return _pub_to_response(pub)


@router.get("/{pub_id}", response_model=PublicationResponse)
def get_publication_detail(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    return _pub_to_response(pub)


@router.put("/{pub_id}", response_model=PublicationResponse)
def update_existing_publication(
    pub_id: str,
    body: PublicationUpdate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    data = body.model_dump(exclude_none=True)
    pub = update_publication(db, pub_id, **data)
    if pub is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    return _pub_to_response(pub)


@router.post("/{pub_id}/submit", response_model=PublicationResponse)
def submit_publication(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    pub = update_publication(db, pub_id, status="submitted", submitted_at=datetime.now(UTC).isoformat())
    if pub is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    return _pub_to_response(pub)


@router.delete("/{pub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_publication(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    delete_publication(get_db_path(), pub_id)


# ── Versions ────────────────────────────────────────────────────────────────────

@router.get("/{pub_id}/versions", response_model=list[VersionResponse])
def list_publication_versions(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    return [
        VersionResponse(
            id=v.id, publication_id=v.publication_id,
            version=v.version, file_path=v.file_path,
            notes=v.notes, created_by=v.created_by,
            created_at=v.created_at,
        )
        for v in list_versions(db, pub_id)
    ]


@router.post("/{pub_id}/versions", response_model=VersionResponse, status_code=status.HTTP_201_CREATED)
def create_publication_version(
    pub_id: str,
    body: VersionCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    v = create_version(db, pub_id, created_by=current_user.id, notes=body.notes)
    return VersionResponse(
        id=v.id, publication_id=v.publication_id,
        version=v.version, file_path=v.file_path,
        notes=v.notes, created_by=v.created_by,
        created_at=v.created_at,
    )


# ── Reviews ─────────────────────────────────────────────────────────────────────

@router.get("/{pub_id}/reviews", response_model=list[ReviewResponse])
def list_publication_reviews(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    return [
        ReviewResponse(
            id=r.id, publication_id=r.publication_id,
            reviewer_name=r.reviewer_name, comments=r.comments,
            decision=r.decision, round=r.round, created_at=r.created_at,
        )
        for r in list_reviews(db, pub_id)
    ]


@router.post("/{pub_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_publication_review(
    pub_id: str,
    body: ReviewCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    r = create_review(
        db, pub_id,
        round=body.round,
        reviewer_name=body.reviewer_name,
        comments=body.comments,
        decision=body.decision,
    )
    return ReviewResponse(
        id=r.id, publication_id=r.publication_id,
        reviewer_name=r.reviewer_name, comments=r.comments,
        decision=r.decision, round=r.round, created_at=r.created_at,
    )
