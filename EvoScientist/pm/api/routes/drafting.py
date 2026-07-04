"""AI paper production — section drafting, revision, reviewer response, experiment-to-section."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from ...crud.experiment_entries import list_entries
from ...crud.experiments import get_experiment, list_experiments, list_linked_tasks
from ...crud.projects import get_project
from ...crud.publications import get_publication, update_publication
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import DraftSectionRequest, ReviewResponseRequest, ReviseRequest

router = APIRouter()
RUNNER_URL = os.getenv("RUNNER_URL", "http://127.0.0.1:8001")

SECTION_PROMPTS = {
    "abstract": """You are a scientific writing assistant. Based on the context below, write a concise **Abstract** (150-250 words). Include: background, objective, methods, key results, and conclusion. Be specific with numbers where available.""",
    "introduction": """You are a scientific writing assistant. Based on the context below, write an **Introduction** (1-2 paragraphs). Cover: the research area and its importance, the specific gap or problem, the objective of this work, and a brief overview of the approach.""",
    "methods": """You are a scientific writing assistant. Based on the context below, write a **Methods** section. Describe: experimental design, materials used, procedures followed, data collection, and analysis methods. Be precise and reproducible.""",
    "results": """You are a scientific writing assistant. Based on the context below, write a **Results** section. Present: key findings clearly, reference specific data points, note statistical significance where applicable. Do not interpret — just report.""",
    "discussion": """You are a scientific writing assistant. Based on the context below, write a **Discussion** section. Cover: interpretation of key findings, how results compare with prior work, limitations, implications, and future directions.""",
    "conclusion": """You are a scientific writing assistant. Based on the context below, write a **Conclusion** (1 paragraph). Summarize the main finding, its significance, and a forward-looking statement.""",
}


def _build_experiment_context(experiment_id: str) -> str:
    db = get_db_path()
    exp = get_experiment(db, experiment_id)
    if not exp:
        return "Experiment not found."
    entries = list_entries(db, experiment_id)
    linked = list_linked_tasks(db, experiment_id)
    parts = [
        f"# Experiment: {exp.name}",
        f"Status: {exp.status}",
        f"Hypothesis: {exp.hypothesis or 'not set'}",
        f"Protocol: {exp.protocol or 'not set'}",
    ]
    if linked:
        parts.append(f"Linked tasks: {', '.join(t.title for t in linked)}")
    if entries:
        parts.append("\n## Entries")
        for e in entries:
            body = (e.body or "")[:800]
            parts.append(f"\n### {e.title} ({e.type})")
            parts.append(body)
    return "\n".join(parts)


def _build_publication_context(pub_id: str) -> str:
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        return "Publication not found."
    parts = [
        f"# Publication: {pub.title}",
        f"Venue: {pub.venue or 'not set'} ({pub.venue_type})",
        f"Status: {pub.status}",
    ]
    if pub.abstract:
        parts.append(f"\n## Current Abstract\n{pub.abstract}")

    if pub.project_id:
        project = get_project(db, pub.project_id)
        if project:
            parts.append(f"\n## Project: {project.name}")
            parts.append(f"Description: {project.description or '(none)'}")
            experiments = list_experiments(db, pub.project_id)
            if experiments:
                parts.append(f"\n## Experiments ({len(experiments)})")
                for exp in experiments:
                    entries = list_entries(db, exp.id)
                    linked = list_linked_tasks(db, exp.id)
                    parts.append(f"\n### {exp.name} (status: {exp.status})")
                    if exp.hypothesis:
                        parts.append(f"Hypothesis: {exp.hypothesis}")
                    if exp.protocol:
                        parts.append(f"Protocol: {exp.protocol}")
                    if linked:
                        parts.append(f"Linked tasks: {', '.join(t.title for t in linked)}")
                    if entries:
                        for e in entries:
                            body = (e.body or "")[:600]
                            parts.append(f"\n#### {e.title} ({e.type})")
                            parts.append(body)
    return "\n".join(parts)


def _build_section_prompt(context: str, section: str, style: str) -> str:
    base = SECTION_PROMPTS.get(section, "Write based on the context below.")
    style_guide = {
        "standard": "Write in a clear, academic style suitable for a peer-reviewed journal.",
        "concise": "Write concisely. Prioritize key information. Aim for 30-50% shorter than standard.",
        "detailed": "Write comprehensively. Include all relevant details, rationale, and nuance.",
        "lay": "Write accessibly for a broader scientific audience. Minimize jargon.",
    }.get(style, "Write in a clear, academic style.")
    return f"""{base}

{style_guide}

Use only the information provided. Where details are missing, note them in **[brackets]**. Do not fabricate data or citations.

---
{context}
---"""


def _build_revise_prompt(current_text: str, instructions: str) -> str:
    return f"""You are a scientific paper editor. Revise the text below according to the instructions.

Instructions: {instructions}

Maintain academic tone and precision. Do not fabricate data or citations.

--- Current text ---
{current_text}
---"""


def _build_review_response_prompt(reviews_text: str, context: str) -> str:
    return f"""You are responding to peer reviewer comments on a scientific manuscript. For each reviewer comment below, write a professional, point-by-point response.

Guidelines:
- Thank the reviewer for each comment
- Address every point directly
- If agreeing, describe the change made
- If disagreeing, provide a reasoned justification
- Be respectful and professional throughout
- Reference specific line numbers or sections where changes were made

--- Manuscript context ---
{context}

--- Reviewer comments ---
{reviews_text}

Write a complete response letter addressed to the editor and reviewers."""


async def _run_agent_and_get_output(run_id: str, prompt: str, workspace_dir: str) -> str | None:
    """Run the writing agent and return the accumulated text output."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{RUNNER_URL}/runs",
                json={
                    "run_id": run_id,
                    "agent_type": "writing",
                    "prompt": prompt,
                    "workspace_dir": workspace_dir,
                },
            )
            if resp.status_code != 200:
                return None

        accumulated: list[str] = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            async with client.stream("GET", f"{RUNNER_URL}/runs/{run_id}/stream") as stream:
                async for line in stream.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            if event.get("type") == "token":
                                accumulated.append(event["data"])
                            elif event.get("type") == "error":
                                return None
                        except Exception:
                            pass
        return "".join(accumulated) or None
    except Exception:
        return None


# ── Section drafting ───────────────────────────────────────────────────────────

@router.post(
    "/publications/{pub_id}/draft-section",
    status_code=status.HTTP_202_ACCEPTED,
)
async def draft_section(
    pub_id: str,
    body: DraftSectionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Draft a specific paper section (abstract, introduction, methods, results, discussion, conclusion)."""
    pub = get_publication(get_db_path(), pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    context = _build_publication_context(pub_id)
    prompt = _build_section_prompt(context, body.section, body.style)

    workspace_base = os.getenv("EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs"))
    workspace_dir = str(Path(workspace_base) / "sections" / f"{pub_id}-{body.section}")
    run_id = f"section-{pub_id}-{body.section}"

    from ...crud.publications import create_version
    create_version(
        get_db_path(), pub_id,
        created_by=current_user.id,
        notes=f"AI drafted section: {body.section} ({body.style}) — in progress",
    )

    background_tasks.add_task(_run_section_and_save, pub_id, body.section, run_id, prompt, workspace_dir)

    return {
        "publication_id": pub_id,
        "section": body.section,
        "style": body.style,
        "status": "drafting",
    }


async def _run_section_and_save(pub_id: str, section: str, run_id: str, prompt: str, workspace_dir: str) -> None:
    text = await _run_agent_and_get_output(run_id, prompt, workspace_dir)
    if text:
        db = get_db_path()
        pub = get_publication(db, pub_id)
        existing = pub.abstract or ""
        if section == "abstract":
            # Save section content as additional context — append to abstract as a marker
            new_abstract = f"{existing}\n\n--- AI-generated {section} ---\n{text[:800]}"
            update_publication(db, pub_id, abstract=new_abstract.strip())
        from ...crud.publications import create_version
        create_version(
            db, pub_id,
            created_by="agent",
            notes=f"AI-generated {section} ({pub_id})",
        )


# ── Draft from experiment (experiment-to-section) ────────────────────────────

@router.post(
    "/projects/{project_id}/experiments/{experiment_id}/draft-to-publication",
    status_code=status.HTTP_202_ACCEPTED,
)
async def draft_from_experiment(
    project_id: str,
    experiment_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
    section: str = Query(default="results", description="Paper section to generate"),
    style: str = Query(default="standard", description="Writing style"),
):
    """Draft a paper section from a specific experiment's data. Creates a publication if none exists."""
    db = get_db_path()
    exp = get_experiment(db, experiment_id)
    if not exp or exp.project_id != project_id:
        raise HTTPException(status_code=404, detail="Experiment not found")

    context = _build_experiment_context(experiment_id)

    # Find or create a publication linked to this project
    from ...crud.publications import create_publication, list_publications
    pubs = list_publications(db, project_id=project_id)
    pub = pubs[0] if pubs else create_publication(
        db,
        title=f"Draft from: {exp.name}",
        created_by=current_user.id,
        project_id=project_id,
        venue_type="preprint",
    )

    prompt = _build_section_prompt(context, section, style)
    workspace_base = os.getenv("EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs"))
    workspace_dir = str(Path(workspace_base) / "sections" / f"exp-{experiment_id}")
    run_id = f"exp-{experiment_id}-{section}"

    background_tasks.add_task(_run_section_and_save, pub.id, section, run_id, prompt, workspace_dir)

    return {
        "publication_id": pub.id,
        "experiment_id": experiment_id,
        "section": section,
        "status": "drafting",
    }


# ── Revision ───────────────────────────────────────────────────────────────────

@router.post(
    "/publications/{pub_id}/revise",
    status_code=status.HTTP_202_ACCEPTED,
)
async def revise_publication(
    pub_id: str,
    body: ReviseRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Revise existing publication text (abstract or full body)."""
    pub = get_publication(get_db_path(), pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    current_text = body.text or pub.abstract or ""
    if not current_text:
        raise HTTPException(status_code=400, detail="No text to revise. Provide text or ensure publication has an abstract.")

    prompt = _build_revise_prompt(current_text, body.instructions)

    workspace_base = os.getenv("EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs"))
    workspace_dir = str(Path(workspace_base) / "revisions" / pub_id)
    run_id = f"revise-{pub_id}"

    from ...crud.publications import create_version
    create_version(
        get_db_path(), pub_id,
        created_by=current_user.id,
        notes=f"AI revision: {body.instructions[:80]}{'…' if len(body.instructions) > 80 else ''}",
    )

    background_tasks.add_task(_run_revision_and_save, pub_id, run_id, prompt, workspace_dir)

    return {
        "publication_id": pub_id,
        "status": "revising",
    }


async def _run_revision_and_save(pub_id: str, run_id: str, prompt: str, workspace_dir: str) -> None:
    text = await _run_agent_and_get_output(run_id, prompt, workspace_dir)
    if text:
        db = get_db_path()
        pub = get_publication(db, pub_id)
        existing_abstract = pub.abstract or ""
        new_abstract = f"{existing_abstract}\n\n--- AI Revision ---\n{text[:800]}"
        update_publication(db, pub_id, abstract=new_abstract.strip())


# ── Reviewer response ─────────────────────────────────────────────────────────

@router.post(
    "/publications/{pub_id}/respond-to-reviewers",
    status_code=status.HTTP_202_ACCEPTED,
)
async def respond_to_reviewers(
    pub_id: str,
    body: ReviewResponseRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Generate a point-by-point response to reviewer comments."""
    pub = get_publication(get_db_path(), pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    context = _build_publication_context(pub_id)
    prompt = _build_review_response_prompt(body.reviewer_comments, context)

    workspace_base = os.getenv("EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs"))
    workspace_dir = str(Path(workspace_base) / "responses" / pub_id)
    run_id = f"response-{pub_id}"

    background_tasks.add_task(
        _run_response_and_save, pub_id, body.reviewer_comments, run_id, prompt, workspace_dir,
    )

    return {
        "publication_id": pub_id,
        "status": "generating",
    }


async def _run_response_and_save(pub_id: str, comments: str, run_id: str, prompt: str, workspace_dir: str) -> None:
    text = await _run_agent_and_get_output(run_id, prompt, workspace_dir)
    if text:
        db = get_db_path()
        from ...crud.publications import create_version
        create_version(
            db, pub_id,
            created_by="agent",
            notes=f"AI-generated reviewer response ({len(comments)} chars of comments)",
        )


# ── Full paper draft (kept for backward compatibility) ────────────────────────

@router.post(
    "/projects/{project_id}/draft-paper",
    status_code=status.HTTP_202_ACCEPTED,
)
async def draft_paper_from_project(
    project_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Collect project experiment data and dispatch the writing agent to draft a complete paper."""
    from ...crud.publications import create_publication
    from .drafting_helpers import _build_draft_prompt, _build_project_context

    context = _build_project_context(project_id)
    db = get_db_path()
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    prompt = _build_draft_prompt(context)
    pub = create_publication(
        db,
        title=f"Draft: {project.name} — AI Generated",
        created_by=current_user.id,
        project_id=project_id,
        venue_type="preprint",
        abstract="AI-generated draft (in progress).",
    )

    workspace_base = os.getenv("EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs"))
    workspace_dir = str(Path(workspace_base) / "drafts" / pub.id)
    background_tasks.add_task(_run_draft_agent, pub.id, prompt, workspace_dir)

    return {
        "publication_id": pub.id,
        "status": "drafting",
    }


async def _run_draft_agent(pub_id: str, prompt: str, workspace_dir: str) -> None:
    from ...crud.publications import update_publication as _up
    text = await _run_agent_and_get_output(f"draft-{pub_id}", prompt, workspace_dir)
    if text:
        abstract = text[:500].strip()
        _up(get_db_path(), pub_id, abstract=abstract, status="draft")
