"""Automated literature review — research agent searches, summarizes, and saves findings."""

from __future__ import annotations

from functools import partial

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from ...crud.ai_jobs import create_job, run_tracked
from ...crud.experiment_entries import create_entry
from ...crud.experiments import create_experiment
from ...crud.projects import get_project
from ...db import get_db_path
from ...models import User
from ..deps import require_project_role
from ..schemas import LiteratureReviewRequest

router = APIRouter()

_LIT_REVIEW_PROMPT = """You are a research literature review specialist. Your task is to conduct a thorough literature review on the topic below and produce a structured Markdown report.

**Topic**: {topic}
**Focus**: {focus}
**Depth**: {depth}

Your report must include:

## Summary
A 2-3 paragraph synthesis of the current state of knowledge on this topic.

## Key Papers
For each of the 5-10 most important papers, include:
- Title and year
- Authors and venue
- Key findings relevant to this topic
- How it relates to the research question
- Strengths and limitations

## Research Gaps
Identify 3-5 specific gaps or unanswered questions in the literature.

## Methodological Approaches
Survey the main experimental approaches used in this area, their strengths and weaknesses.

## Future Directions
Suggest 2-3 promising research directions based on the literature.

## References
List all papers cited in the review.

Guidelines:
- Use web search (tavily) to find relevant papers
- Focus on recent work (last 5 years) unless seminal papers are relevant
- Be critical — note methodological concerns and conflicting findings
- Do not fabricate papers or citations
- Be specific — include numbers, statistics, and concrete findings where available"""


@router.post("/projects/{project_id}/literature-review", status_code=status.HTTP_202_ACCEPTED)
async def run_literature_review(
    project_id: str,
    body: LiteratureReviewRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Launch an automated literature review using the research agent."""
    project = get_project(get_db_path(), project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    prompt = _LIT_REVIEW_PROMPT.format(
        topic=body.topic,
        focus=body.focus_area or "general",
        depth=body.depth,
    )
    from ....paths import RUNS_DIR
    run_id = f"litreview-{project_id}-{__import__('time').time():.0f}"
    workspace_dir = str(RUNS_DIR / "research" / run_id)

    job = create_job(get_db_path(), kind="literature-review", title=f"Literature review: {body.topic[:80]}",
                     user_id=current_user.id, project_id=project_id)
    background_tasks.add_task(run_tracked, job.id, partial(
        _run_lit_review, project_id, current_user.id, run_id, prompt, workspace_dir, body.topic))
    return {"status": "started", "message": f"Literature review started for '{body.topic}'", "job_id": job.id}


async def _run_lit_review(
    project_id: str, user_id: str, run_id: str, prompt: str, workspace_dir: str, topic: str,
) -> str | None:
    from ...crud.ai_usage import UsageContext
    from .drafting import _run_agent_and_get_output

    text = await _run_agent_and_get_output(
        run_id, prompt, workspace_dir, agent_type="research",
        context=UsageContext(task="literature-review", user_id=user_id, project_id=project_id),
    )
    if not text:
        return None
    db = get_db_path()
    exp = create_experiment(db, project_id=project_id, name=f"Literature Review: {topic[:80]}", created_by=user_id)
    create_entry(db, experiment_id=exp.id, entry_type="result", title=f"Literature Review — {topic}", body=text, author_id=user_id)
    return f"/projects/{project_id}/experiments?exp={exp.id}"
