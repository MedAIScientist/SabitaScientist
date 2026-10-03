"""Check a publication's references against CrossRef, OpenAlex, arXiv, PMC and Semantic Scholar."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ... import citations
from ...crud.publications import get_publication, list_versions
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user

router = APIRouter()


class VerifyReferences(BaseModel):
    text: str | None = Field(default=None, max_length=400_000)  # default: the latest draft


@router.post("/publications/{pub_id}/references/verify")
def verify_references(pub_id: str, body: VerifyReferences, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    if get_publication(db, pub_id) is None:
        raise HTTPException(404, "Publication not found")
    text = body.text
    if not text:
        drafts = [v for v in list_versions(db, pub_id) if v.content]
        if not drafts:
            raise HTTPException(400, "no draft text to check; paste the references")
        text = max(drafts, key=lambda v: v.version).content
    result = citations.verify_text(text or "")
    if not result["references"]:
        raise HTTPException(400, "no references found: add a 'References' heading or BibTeX entries")
    return result
