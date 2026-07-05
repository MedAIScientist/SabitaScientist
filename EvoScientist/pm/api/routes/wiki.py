from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

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
from ..deps import get_current_user

router = APIRouter()


@router.get("/labs/{lab_id}/wiki")
def list_wiki_pages(
    lab_id: str,
    current_user: User = Depends(get_current_user),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return [
        {
            "id": p.id,
            "title": p.title,
            "slug": p.slug,
            "tags": p.tags,
            "updated_at": p.updated_at,
            "created_by": p.created_by,
        }
        for p in list_pages(get_db_path(), lab_id, offset, limit)
    ]


@router.post("/labs/{lab_id}/wiki", status_code=201)
def create_wiki_page(
    lab_id: str, body: dict, current_user: User = Depends(get_current_user)
):
    p = create_page(
        get_db_path(),
        lab_id,
        title=body["title"],
        content=body.get("content", ""),
        tags=body.get("tags"),
        created_by=current_user.id,
    )
    return {"id": p.id, "title": p.title, "slug": p.slug}


@router.get("/labs/{lab_id}/wiki/{page_id}")
def get_wiki_page(
    page_id: str, lab_id: str, current_user: User = Depends(get_current_user)
):
    p = get_page(get_db_path(), page_id)
    if not p or p.lab_id != lab_id:
        raise HTTPException(404)
    return {
        "id": p.id,
        "title": p.title,
        "slug": p.slug,
        "content": p.content,
        "tags": p.tags,
        "created_by": p.created_by,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


@router.get("/labs/{lab_id}/wiki/slug/{slug}")
def get_wiki_page_by_slug(
    slug: str, lab_id: str, current_user: User = Depends(get_current_user)
):
    p = get_page_by_slug(get_db_path(), lab_id, slug)
    if not p:
        raise HTTPException(404)
    return {
        "id": p.id,
        "title": p.title,
        "slug": p.slug,
        "content": p.content,
        "tags": p.tags,
        "created_by": p.created_by,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


@router.put("/labs/{lab_id}/wiki/{page_id}")
def update_wiki_page(
    page_id: str,
    lab_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
):
    p = update_page(
        get_db_path(),
        page_id,
        content=body.get("content"),
        title=body.get("title"),
        tags=body.get("tags"),
    )
    if not p:
        raise HTTPException(404)
    return {"id": p.id, "title": p.title, "slug": p.slug}


@router.delete("/labs/{lab_id}/wiki/{page_id}", status_code=204)
def delete_wiki_page(
    page_id: str, lab_id: str, current_user: User = Depends(get_current_user)
):
    delete_page(get_db_path(), page_id)
