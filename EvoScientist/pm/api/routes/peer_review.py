"""AI-powered peer review workflow — assign reviewers, generate reviews, track decisions."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from ...crud.publications import (
    create_review,
    get_publication,
    list_reviews,
    update_publication,
)
from ...crud.users import get_user_by_id
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user
from ..schemas import ReviewAssignmentRequest

router = APIRouter()
RUNNER_URL = os.getenv("RUNNER_URL", "http://127.0.0.1:8001")

_REVIEW_PROMPT = """You are an expert peer reviewer for a scientific journal. Review the publication context below and produce a structured review.

## Manuscript
Title: {title}
Abstract: {abstract}

## Review Guidelines

Review the manuscript across these dimensions:

### 1. Summary
Briefly summarize what the paper does.

### 2. Major Issues
List each major issue with:
- **Issue**: What is the problem?
- **Severity**: High / Medium / Low
- **Justification**: Why this matters
- **Suggested Fix**: How to address it

### 3. Minor Issues
List minor concerns (writing clarity, figure quality, missing references, etc.)

### 4. Methodology Assessment
- Is the approach sound?
- Are the methods described sufficiently?
- Are the controls adequate?
- Are statistical methods appropriate?

### 5. Novelty & Significance
- How novel is this work?
- What is the potential impact?

### 6. Overall Recommendation
Choose one: **Accept**, **Minor Revision**, **Major Revision**, or **Reject**
Provide a brief justification.

Be constructive, specific, and professional. Reference specific parts of the manuscript where relevant.

--- Manuscript Context ---
{context}"""


@router.post("/publications/{pub_id}/assign-reviewer")
def assign_reviewer(
    pub_id: str,
    body: ReviewAssignmentRequest,
    current_user: User = Depends(get_current_user),
):
    """Assign a reviewer to a publication for internal peer review."""
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(404, "Publication not found")

    reviewer = get_user_by_id(db, body.reviewer_id)
    if not reviewer:
        raise HTTPException(404, "Reviewer not found")

    review = create_review(
        db, pub_id,
        round=body.round or 1,
        reviewer_name=reviewer.username,
    )
    update_publication(db, pub_id, status="reviewing")

    from ...notifications import notify_admission_review
    if reviewer.email:
        notify_admission_review(reviewer.email, pub.title, pub_id)

    return {
        "review_id": review.id,
        "publication_id": pub_id,
        "reviewer": reviewer.username,
        "status": "assigned",
    }


@router.post("/publications/{pub_id}/generate-ai-review", status_code=status.HTTP_202_ACCEPTED)
async def generate_ai_review(
    pub_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Use the research agent to generate an AI peer review of a publication."""
    from ...api.routes.drafting import _build_publication_context

    pub = get_publication(get_db_path(), pub_id)
    if not pub:
        raise HTTPException(404, "Publication not found")

    context = _build_publication_context(pub_id)
    prompt = _REVIEW_PROMPT.format(title=pub.title, abstract=pub.abstract or "(no abstract)", context=context)

    run_id = f"review-{pub_id}-{__import__('time').time():.0f}"
    workspace_base = os.getenv("EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs"))
    workspace_dir = str(Path(workspace_base) / "reviews" / run_id)

    background_tasks.add_task(_run_ai_review, pub_id, run_id, prompt, workspace_dir)
    return {"status": "started", "publication_id": pub_id}


async def _run_ai_review(pub_id: str, run_id: str, prompt: str, workspace_dir: str) -> None:
    db = get_db_path()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{RUNNER_URL}/runs", json={
                "run_id": run_id, "agent_type": "research",
                "prompt": prompt, "workspace_dir": workspace_dir,
            })
            if resp.status_code != 200:
                return

        accumulated: list[str] = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            async with client.stream("GET", f"{RUNNER_URL}/runs/{run_id}/stream") as stream:
                async for line in stream.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = __import__("json").loads(line[6:])
                            if ev.get("type") == "token":
                                accumulated.append(ev["data"])
                            elif ev.get("type") == "error":
                                return
                        except Exception:
                            pass

        text = "".join(accumulated)
        if text:
            # Extract decision from the review text
            decision = None
            for d in ["accept", "minor_revision", "major_revision", "reject"]:
                if d.lower() in text[:500].lower():
                    decision = d
                    break
            create_review(db, pub_id, round=1, reviewer_name="AI Reviewer", comments=text[:2000], decision=decision)
    except Exception:
        pass


@router.get("/publications/{pub_id}/reviews")
def list_publication_reviews(pub_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    return [
        {
            "id": r.id, "reviewer_name": r.reviewer_name,
            "comments": r.comments, "decision": r.decision,
            "round": r.round, "created_at": r.created_at,
        }
        for r in list_reviews(db, pub_id)
    ]
