"""AI-powered peer review workflow — assign reviewers, generate reviews, track decisions."""

from __future__ import annotations

from functools import partial

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from ....paths import RUNS_DIR
from ...crud.ai_jobs import create_job, run_tracked
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
    workspace_dir = str(RUNS_DIR / "reviews" / run_id)

    job = create_job(get_db_path(), kind="ai-peer-review", title=f"AI review: {pub.title[:80]}",
                     user_id=current_user.id, project_id=pub.project_id, publication_id=pub_id)
    background_tasks.add_task(run_tracked, job.id, partial(
        _run_ai_review, pub_id, run_id, prompt, workspace_dir, current_user.id))
    return {"status": "started", "publication_id": pub_id, "job_id": job.id}


async def _run_ai_review(pub_id: str, run_id: str, prompt: str, workspace_dir: str, user_id: str) -> str | None:
    from ...crud.ai_usage import UsageContext
    from .drafting import _run_agent_and_get_output

    text = await _run_agent_and_get_output(
        run_id, prompt, workspace_dir, agent_type="research",
        context=UsageContext(task="ai-peer-review", user_id=user_id, publication_id=pub_id),
    )
    if not text:
        return None
    # Extract decision from the review text
    decision = next((d for d in ("accept", "minor_revision", "major_revision", "reject")
                     if d in text[:500].lower()), None)
    create_review(get_db_path(), pub_id, round=1, reviewer_name="AI Reviewer", comments=text[:2000], decision=decision)
    return f"/publications/{pub_id}"


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
