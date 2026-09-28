"""Patent drafting — AI-generated patent disclosure drafts."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..._ai import run_llm_direct_async
from ...crud.projects import get_project
from ...db import get_db_path
from ...models import User
from ..deps import require_project_role

router = APIRouter()


class PatentDraftRequest(BaseModel):
    invention_title: str = Field(min_length=1)
    field: str = Field(default="wireless communications")
    key_innovation: str | None = None
    technical_details: str | None = None


_PATENT_SYSTEM = """You are a patent drafting assistant. Generate a professional patent disclosure draft suitable for filing. Follow standard patent structure:

1. Title of Invention
2. Technical Field
3. Background
4. Summary
5. Brief Description of Drawings
6. Detailed Description
7. Claims (at least 3)
8. Abstract

Use precise technical language. Do not fabricate prior art references. Mark any speculative elements as [provisional]."""


@router.post("/projects/{project_id}/draft-patent", status_code=status.HTTP_202_ACCEPTED)
async def draft_patent(
    project_id: str,
    body: PatentDraftRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    p = get_project(get_db_path(), project_id)
    if not p:
        raise HTTPException(404, "Project not found")

    prompt = f"""Invention Title: {body.invention_title}
Field: {body.field}
Key Innovation: {body.key_innovation or 'Not specified'}
Technical Details: {body.technical_details or 'Not specified'}

Generate a complete patent disclosure draft for the above invention."""

    text = await run_llm_direct_async(
        system_prompt=_PATENT_SYSTEM,
        user_prompt=prompt,
        temperature=0.2,
    )

    from ...crud.experiment_entries import create_entry
    from ...crud.experiments import list_experiments as _list_exps

    exps = _list_exps(get_db_path(), project_id)
    if exps:
        create_entry(
            get_db_path(), experiment_id=exps[0].id,
            entry_type="note", title=f"Patent Draft: {body.invention_title}",
            body=text, author_id=current_user.id,
        )

    return {"status": "drafted", "invention_title": body.invention_title, "output": text[:500]}
