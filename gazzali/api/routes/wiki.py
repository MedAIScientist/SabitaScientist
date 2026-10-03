"""Lab wiki page management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ...crud.wiki import (
    create_page,
    delete_page,
    get_page,
    get_page_by_slug,
    list_pages,
    update_page,
)
from ...db import get_db_path
from ...models import User
from ..audit_helper import log_action
from ..deps import require_lab_member
from ..schemas import WikiPageCreate, WikiPageResponse, WikiPageUpdate

router = APIRouter()


@router.get("/labs/{lab_id}/wiki", response_model=list[WikiPageResponse])
def list_wiki_pages(
    lab_id: str,
    current_user: User = Depends(require_lab_member()),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_db_path()
    return [
        WikiPageResponse(
            id=p.id,
            lab_id=p.lab_id,
            title=p.title,
            slug=p.slug,
            content=p.content,
            tags=p.tags or [],
            created_by=p.created_by,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in list_pages(db, lab_id, offset, limit)
    ]


@router.post(
    "/labs/{lab_id}/wiki",
    response_model=WikiPageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_wiki_page(
    request: Request,
    lab_id: str,
    body: WikiPageCreate,
    current_user: User = Depends(require_lab_member()),
):
    db = get_db_path()
    p = create_page(
        db,
        lab_id=lab_id,
        title=body.title,
        content=body.content,
        tags=body.tags,
        created_by=current_user.id,
    )
    log_action(request, current_user, "create", "wiki_page", p.id, f"title={p.title}")
    return WikiPageResponse(
        id=p.id,
        lab_id=p.lab_id,
        title=p.title,
        slug=p.slug,
        content=p.content,
        tags=p.tags or [],
        created_by=p.created_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("/labs/{lab_id}/wiki/{page_id}", response_model=WikiPageResponse)
def get_wiki_page(
    page_id: str,
    lab_id: str,
    current_user: User = Depends(require_lab_member()),
):
    db = get_db_path()
    p = get_page(db, page_id)
    if not p or p.lab_id != lab_id:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    return WikiPageResponse(
        id=p.id,
        lab_id=p.lab_id,
        title=p.title,
        slug=p.slug,
        content=p.content,
        tags=p.tags or [],
        created_by=p.created_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("/labs/{lab_id}/wiki/slug/{slug}", response_model=WikiPageResponse)
def get_wiki_page_by_slug(
    slug: str,
    lab_id: str,
    current_user: User = Depends(require_lab_member()),
):
    db = get_db_path()
    p = get_page_by_slug(db, lab_id, slug)
    if not p:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    return WikiPageResponse(
        id=p.id,
        lab_id=p.lab_id,
        title=p.title,
        slug=p.slug,
        content=p.content,
        tags=p.tags or [],
        created_by=p.created_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.put("/labs/{lab_id}/wiki/{page_id}", response_model=WikiPageResponse)
def update_wiki_page(
    request: Request,
    page_id: str,
    lab_id: str,
    body: WikiPageUpdate,
    current_user: User = Depends(require_lab_member()),
):
    db = get_db_path()
    p = update_page(
        db,
        page_id,
        content=body.content,
        title=body.title,
        tags=body.tags,
    )
    if not p:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    log_action(
        request, current_user, "update", "wiki_page", page_id, f"title={p.title}"
    )
    return WikiPageResponse(
        id=p.id,
        lab_id=p.lab_id,
        title=p.title,
        slug=p.slug,
        content=p.content,
        tags=p.tags or [],
        created_by=p.created_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.delete("/labs/{lab_id}/wiki/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wiki_page(
    request: Request,
    page_id: str,
    lab_id: str,
    current_user: User = Depends(require_lab_member()),
):
    db = get_db_path()
    p = get_page(db, page_id)
    if p and p.lab_id == lab_id:
        log_action(
            request, current_user, "delete", "wiki_page", page_id, f"title={p.title}"
        )
    delete_page(db, page_id)
