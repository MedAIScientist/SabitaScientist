"""AI paper production — section drafting, revision, reviewer response, experiment-to-section."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from ....paths import RUNS_DIR
from ..._evoscientist import get_runner_url
from ...crud.ai_usage import UsageContext
from ...crud.experiment_entries import create_entry, list_entries
from ...crud.experiments import (
    create_experiment,
    get_experiment,
    list_experiments,
    list_linked_tasks,
)
from ...crud.projects import get_project
from ...crud.publications import (
    create_publication,
    create_version,
    get_publication,
    list_linked_experiments,
    list_publications,
    update_publication,
)
from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import (
    CitationVerificationRequest,
    DraftSectionRequest,
    HypothesisRequest,
    MethodologyValidationRequest,
    ResearchIdeationRequest,
    ReviewResponseRequest,
    ReviseRequest,
)
from .drafting_helpers import (
    GROUNDING_RULE,
    _entry_body,
    prompt_fingerprint,
    render_metrics_block,
)

router = APIRouter()
RUNNER_URL = get_runner_url()

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
    parts.append(render_metrics_block(experiment_id))
    if entries:
        parts.append("\n## Entries")
        for e in entries:
            parts.append(f"\n### {e.title} ({e.type})")
            parts.append(_entry_body(e))
    return "\n".join(parts)


def _build_publication_context(pub_id: str, section: str | None = None) -> str:
    """Build grounding context for a paper draft.

    When ``section`` is set and the publication has experiment links
    (``publication_experiments``), only experiments linked to that section
    (or with no section tag) are included — the scoped-evidence path.
    Always appends the weekly evidence pack when any related updates exist.
    """
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

    # Prefer explicitly linked experiments (optionally section-scoped).
    linked_rows = list_linked_experiments(db, pub_id)
    linked_by_id = {row["experiment_id"]: row.get("section") for row in linked_rows}

    def _exp_in_scope(exp_id: str, exp_project_id: str | None) -> bool:
        if section and linked_by_id:
            if exp_id in linked_by_id:
                linked_section = linked_by_id[exp_id]
                return linked_section in (None, "", section)
            return False
        if linked_by_id:
            return exp_id in linked_by_id
        # Fallback: whole project (legacy behaviour)
        return pub.project_id is not None and exp_project_id == pub.project_id

    experiments: list = []
    if linked_by_id:
        for exp_id in linked_by_id:
            exp = get_experiment(db, exp_id)
            if exp and _exp_in_scope(exp_id, exp.project_id):
                experiments.append(exp)
    elif pub.project_id:
        project = get_project(db, pub.project_id)
        if project:
            parts.append(f"\n## Project: {project.name}")
            parts.append(f"Description: {project.description or '(none)'}")
            experiments = [
                e for e in list_experiments(db, pub.project_id) if _exp_in_scope(e.id, e.project_id)
            ]

    if section:
        parts.append(f"\n## Target section: {section}")
        parts.append(
            "Write ONLY this section. Use the linked experiment evidence below; "
            "do not invent results that are not present."
        )

    if experiments:
        scope_label = f" (scoped to {section})" if section else ""
        parts.append(f"\n## Linked Experiments ({len(experiments)}){scope_label}")
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
            parts.append(render_metrics_block(exp.id))
            if entries:
                for e in entries:
                    parts.append(f"\n#### {e.title} ({e.type})")
                    parts.append(_entry_body(e))

    evidence = _build_evidence_pack(db, pub_id, list(linked_by_id.keys()))
    if evidence:
        parts.append(evidence)

    return "\n".join(parts)


def _build_evidence_pack(db, pub_id: str, experiment_ids: list[str]) -> str:
    """Collect weekly-report updates that mention this paper or its experiments.

    Sources: ``weekly_report_items`` linked by publication_id/experiment_id, plus
    free-text item titles containing the publication title. Used as Intro/Related
    bullets and open questions for the writer.
    """
    pub = get_publication(db, pub_id)
    if not pub:
        return ""
    title_like = (pub.title or "").strip().lower()

    with get_db(db) as conn:
        clauses = ["i.publication_id = ?"]
        params: list = [pub_id]
        if experiment_ids:
            clauses.append(f"i.experiment_id IN ({','.join('?' * len(experiment_ids))})")
            params.extend(experiment_ids)
        rows = conn.execute(
            f"""SELECT i.item_title, i.item_kind, i.progress_pct, i.status,
                       i.what_changed, i.next_step, i.needs_help, i.blocker,
                       i.risk_level, i.next_deadline, r.week_start
                FROM weekly_report_items i
                JOIN weekly_reports r ON r.id = i.report_id
                WHERE ({' OR '.join(clauses)}) AND r.status = 'submitted'
                ORDER BY r.week_start DESC LIMIT 25""",
            params,
        ).fetchall()

        if not rows and title_like:
            # Fuzzy: item titles that share the publication title tokens
            rows = conn.execute(
                """SELECT i.item_title, i.item_kind, i.progress_pct, i.status,
                          i.what_changed, i.next_step, i.needs_help, i.blocker,
                          i.risk_level, i.next_deadline, r.week_start
                   FROM weekly_report_items i
                   JOIN weekly_reports r ON r.id = i.report_id
                   WHERE r.status = 'submitted' AND lower(i.item_title) LIKE ?
                   ORDER BY r.week_start DESC LIMIT 15""",
                (f"%{title_like[:40]}%",),
            ).fetchall()

    if not rows:
        return ""

    parts = [
        "\n## Weekly evidence pack (from supervision updates)",
        "Use these as grounding for contributions, results narrative, and open questions. "
        "Do not fabricate metrics beyond what is listed.",
    ]
    for r in rows:
        parts.append(f"\n### [{r['week_start']}] {r['item_title']} ({r['item_kind'] or 'work'})")
        parts.append(f"Progress: {r['progress_pct']}% · status: {r['status'] or 'n/a'} · risk: {r['risk_level']}")
        if r["what_changed"]:
            parts.append(f"What changed: {r['what_changed']}")
        if r["next_step"]:
            parts.append(f"Next step: {r['next_step']}")
        if r["needs_help"]:
            blocker = f" — {r['blocker']}" if r["blocker"] else ""
            parts.append(f"OPEN QUESTION: help needed{blocker}")
        if r["next_deadline"]:
            parts.append(f"Deadline: {r['next_deadline']}")
    return "\n".join(parts)


def _save_section_file(workspace_dir: str, section: str, text: str) -> str:
    """Save generated section text to a file and return the file path."""
    path = Path(workspace_dir) / f"{section}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


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
---
{GROUNDING_RULE}"""


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


def _publication_context(pub_id: str, user_id: str, task: str) -> UsageContext:
    """Usage attribution for AI work done on one publication.

    The project is resolved from the publication so those tokens also appear in
    project-level reporting, not only against the paper.
    """
    pub = get_publication(get_db_path(), pub_id)
    return UsageContext(
        task=task,
        user_id=user_id,
        project_id=pub.project_id if pub else None,
        publication_id=pub_id,
    )


async def _run_agent_and_get_output(
    run_id: str,
    prompt: str,
    workspace_dir: str,
    agent_type: str = "writing",
    context: UsageContext | None = None,
) -> str | None:
    """Run an agent (research/code/data_analysis/writing) and return the accumulated text output.

    ``context`` travels with the request so the runner can attribute the tokens it
    burns to the person and the paper that asked for them.
    """
    try:
        payload = {
            "run_id": run_id,
            "agent_type": agent_type,
            "prompt": prompt,
            "workspace_dir": workspace_dir,
        }
        if context is not None:
            payload.update(
                task=context.task,
                user_id=context.user_id,
                project_id=context.project_id,
                publication_id=context.publication_id,
            )
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{RUNNER_URL}/runs", json=payload)
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

    context = _build_publication_context(pub_id, section=body.section)
    prompt = _build_section_prompt(context, body.section, body.style)

    workspace_dir = str(RUNS_DIR / "sections" / f"{pub_id}-{body.section}")
    run_id = f"section-{pub_id}-{body.section}"

    create_version(
        get_db_path(), pub_id,
        created_by=current_user.id,
        notes=f"AI drafted section: {body.section} ({body.style}) — in progress",
    )

    background_tasks.add_task(_run_section_and_save, pub_id, body.section, run_id, prompt, workspace_dir, current_user.id)

    return {
        "publication_id": pub_id,
        "section": body.section,
        "style": body.style,
        "status": "drafting",
    }


async def _run_section_and_save(pub_id: str, section: str, run_id: str, prompt: str, workspace_dir: str, user_id: str) -> None:
    text = await _run_agent_and_get_output(
        run_id, prompt, workspace_dir,
        context=_publication_context(pub_id, user_id, "draft-section"),
    )
    if text:
        db = get_db_path()
        file_path = _save_section_file(workspace_dir, section, text)
        create_version(
            db, pub_id,
            created_by=user_id,
            file_path=file_path,
            notes=f"AI-generated {section} ({len(text)} chars)",
            content=text,
            section=section,
            generated_by="ai-agent",
            prompt_hash=prompt_fingerprint(prompt),
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
    pubs = list_publications(db, project_id=project_id)
    pub = pubs[0] if pubs else create_publication(
        db,
        title=f"Draft from: {exp.name}",
        created_by=current_user.id,
        project_id=project_id,
        venue_type="preprint",
    )

    prompt = _build_section_prompt(context, section, style)
    workspace_dir = str(RUNS_DIR / "sections" / f"exp-{experiment_id}")
    run_id = f"exp-{experiment_id}-{section}"

    background_tasks.add_task(_run_section_and_save, pub.id, section, run_id, prompt, workspace_dir, current_user.id)

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

    workspace_dir = str(RUNS_DIR / "revisions" / pub_id)
    run_id = f"revise-{pub_id}"

    create_version(
        get_db_path(), pub_id,
        created_by=current_user.id,
        notes=f"AI revision: {body.instructions[:80]}{'…' if len(body.instructions) > 80 else ''}",
    )

    background_tasks.add_task(_run_revision_and_save, pub_id, run_id, prompt, workspace_dir, current_user.id)

    return {
        "publication_id": pub_id,
        "status": "revising",
    }


async def _run_revision_and_save(pub_id: str, run_id: str, prompt: str, workspace_dir: str, user_id: str) -> None:
    text = await _run_agent_and_get_output(
        run_id, prompt, workspace_dir,
        context=_publication_context(pub_id, user_id, "revise"),
    )
    if text:
        db = get_db_path()
        file_path = _save_section_file(workspace_dir, "revision", text)
        create_version(
            db, pub_id,
            created_by="system",
            file_path=file_path,
            notes=f"AI revision ({len(text)} chars)",
            content=text,
            section="revision",
            generated_by="ai-agent",
            prompt_hash=prompt_fingerprint(prompt),
        )


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

    workspace_dir = str(RUNS_DIR / "responses" / pub_id)
    run_id = f"response-{pub_id}"

    background_tasks.add_task(
        _run_response_and_save, pub_id, body.reviewer_comments, run_id, prompt, workspace_dir, current_user.id,
    )

    return {
        "publication_id": pub_id,
        "status": "generating",
    }


async def _run_response_and_save(pub_id: str, comments: str, run_id: str, prompt: str, workspace_dir: str, user_id: str) -> None:
    text = await _run_agent_and_get_output(
        run_id, prompt, workspace_dir,
        context=_publication_context(pub_id, user_id, "respond-to-reviewers"),
    )
    if text:
        db = get_db_path()
        file_path = _save_section_file(workspace_dir, "reviewer-response", text)
        create_version(
            db, pub_id,
            created_by=user_id,
            file_path=file_path,
            notes=f"AI-generated reviewer response ({len(comments)} chars of comments)",
            content=text,
            section="reviewer-response",
            generated_by="ai-agent",
            prompt_hash=prompt_fingerprint(prompt),
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

    workspace_dir = str(RUNS_DIR / "drafts" / pub.id)
    background_tasks.add_task(_run_draft_agent, pub.id, prompt, workspace_dir, current_user.id)

    return {
        "publication_id": pub.id,
        "status": "drafting",
    }


async def _run_draft_agent(pub_id: str, prompt: str, workspace_dir: str, user_id: str) -> None:
    text = await _run_agent_and_get_output(
        f"draft-{pub_id}", prompt, workspace_dir,
        context=_publication_context(pub_id, user_id, "draft-paper"),
    )
    if text:
        file_path = _save_section_file(workspace_dir, "full-draft", text)
        # The full text lives in the version row; `abstract` keeps only a preview
        # so the publication list stays readable.
        update_publication(get_db_path(), pub_id, abstract=text[:2000].strip(), status="draft")
        create_version(
            get_db_path(), pub_id,
            created_by="system",
            file_path=file_path,
            notes=f"Full AI-generated draft ({len(text)} chars)",
            content=text,
            section="full-draft",
            generated_by="ai-agent",
            prompt_hash=prompt_fingerprint(prompt),
        )


# ── Hypothesis Generation ──────────────────────────────────────────────────────

_HYPOTHESIS_PROMPT = """You are a research scientist generating testable hypotheses. Based on the topic and context below, generate 3-5 specific, falsifiable hypotheses. Each hypothesis should be:

1. **Specific** — clearly defined variables and predicted relationship
2. **Testable** — can be confirmed or refuted through experiment
3. **Novel** — not trivially true or false based on existing knowledge
4. **Grounded** — connected to the provided context

For each hypothesis, include:
- The hypothesis statement
- The rationale (why this is worth testing)
- A suggested experimental approach
- Predicted outcome if true
- Predicted outcome if false

Format as a structured Markdown report.

Topic: {topic}
Additional context:
{context}"""


@router.post("/projects/{project_id}/generate-hypothesis", status_code=status.HTTP_202_ACCEPTED)
async def generate_hypothesis(
    project_id: str,
    body: HypothesisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Use the research agent to generate testable hypotheses based on a topic."""
    project = get_project(get_db_path(), project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    prompt = _HYPOTHESIS_PROMPT.format(topic=body.topic, context=body.context or project.description or "(none provided)")
    run_id = f"hypothesis-{project_id}-{time.time():.0f}"
    workspace_dir = str(RUNS_DIR / "research" / run_id)

    background_tasks.add_task(_save_hypothesis_output, project_id, current_user.id, run_id, prompt, workspace_dir, body.topic)

    return {"status": "generating", "message": "Hypothesis generation started — results will be saved as an experiment entry."}


async def _save_hypothesis_output(
    project_id: str, user_id: str, run_id: str, prompt: str, workspace_dir: str, topic: str,
) -> None:
    text = await _run_agent_and_get_output(
        run_id, prompt, workspace_dir, agent_type="research",
        context=UsageContext(task="generate-hypothesis", user_id=user_id, project_id=project_id),
    )
    if text:
        db = get_db_path()
        exp = create_experiment(db, project_id=project_id, name=f"Hypothesis: {topic[:80]}", created_by=user_id)
        create_entry(db, experiment_id=exp.id, entry_type="result", title=f"AI-Generated Hypotheses for: {topic}", body=text, author_id=user_id)


# ── Research Ideation ──────────────────────────────────────────────────────────

_IDEATION_PROMPT = """You are a research strategist helping a scientist explore new directions. Based on the topic and focus area below, generate {count} distinct research ideas.

For each idea, provide:
1. **Research Question** — a clear, focused question
2. **Rationale** — why this direction is promising
3. **Novelty** — what makes this different from existing work
4. **Feasibility** — estimated difficulty and resource requirements
5. **Potential Impact** — what success would enable
6. **Suggested First Step** — a concrete action to begin

Prioritize ideas that are:
- Novel but build on existing work
- Feasible with reasonable resources
- Impactful if successful
- Aligned with the scientist's domain

Format as a structured Markdown report with clear section headers.

Research Topic: {topic}
Focus Area: {focus_area}"""


@router.post("/projects/{project_id}/research-ideation", status_code=status.HTTP_202_ACCEPTED)
async def research_ideation(
    project_id: str,
    body: ResearchIdeationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Use the research agent to generate novel research directions."""
    project = get_project(get_db_path(), project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    prompt = _IDEATION_PROMPT.format(topic=body.topic, focus_area=body.focus_area or "general", count=body.count)
    run_id = f"ideation-{project_id}-{time.time():.0f}"
    workspace_dir = str(RUNS_DIR / "research" / run_id)

    background_tasks.add_task(_save_ideation_output, project_id, current_user.id, run_id, prompt, workspace_dir, body.topic)

    return {"status": "generating", "message": "Research ideation started — results will be saved as an experiment entry."}


async def _save_ideation_output(
    project_id: str, user_id: str, run_id: str, prompt: str, workspace_dir: str, topic: str,
) -> None:
    text = await _run_agent_and_get_output(
        run_id, prompt, workspace_dir, agent_type="research",
        context=UsageContext(task="research-ideation", user_id=user_id, project_id=project_id),
    )
    if text:
        db = get_db_path()
        exp = create_experiment(db, project_id=project_id, name=f"Ideation: {topic[:80]}", created_by=user_id, status="planned")
        create_entry(db, experiment_id=exp.id, entry_type="result", title=f"Research Ideas for: {topic}", body=text, author_id=user_id)


# ── Methodology Validation ─────────────────────────────────────────────────────

_VALIDATION_PROMPT = """You are a senior methodology reviewer evaluating a proposed experimental approach. Analyze the proposed methods below and provide:

1. **Strengths** — what is well-designed and why
2. **Weaknesses** — potential flaws, confounds, or limitations
3. **Risks** — things that could go wrong and their likelihood
4. **Missing Controls** — necessary controls that are absent
5. **Statistical Concerns** — sample size, power, analysis choices
6. **Reproducibility** — are the methods described sufficiently for replication?
7. **Suggested Improvements** — concrete, actionable changes
8. **Alternative Approaches** — other methods that could work better

Be constructive and specific. Reference established best practices in the field.

--- Proposed Methods ---
{methods}"""


@router.post("/projects/{project_id}/validate-methodology", status_code=status.HTTP_202_ACCEPTED)
async def validate_methodology(
    project_id: str,
    body: MethodologyValidationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Use the research agent to validate proposed experimental methods."""
    project = get_project(get_db_path(), project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    prompt = _VALIDATION_PROMPT.format(methods=body.proposed_methods)
    run_id = f"validation-{project_id}-{time.time():.0f}"
    workspace_dir = str(RUNS_DIR / "research" / run_id)

    background_tasks.add_task(_save_validation_output, project_id, current_user.id, run_id, prompt, workspace_dir)

    return {"status": "generating", "message": "Methodology validation started — results will be saved as an experiment entry."}


async def _save_validation_output(project_id: str, user_id: str, run_id: str, prompt: str, workspace_dir: str) -> None:
    text = await _run_agent_and_get_output(
        run_id, prompt, workspace_dir, agent_type="research",
        context=UsageContext(task="validate-methodology", user_id=user_id, project_id=project_id),
    )
    if text:
        db = get_db_path()
        exp = create_experiment(db, project_id=project_id, name="Methodology Review", created_by=user_id)
        create_entry(db, experiment_id=exp.id, entry_type="result", title="Methodology Validation Report", body=text, author_id=user_id)


# ── Citation Verification ──────────────────────────────────────────────────────

_CITATION_PROMPT = """You are a citation verification specialist. Below is a citation verification report generated by querying the Semantic Scholar database, followed by the original user-provided citations.

For each citation, synthesize the database findings into a clear verdict:
- ✅ **Verified** — found in Semantic Scholar with matching title/authors/year. Include citation count and venue.
- ⚠️ **Partial match** — found a paper with similar title but details differ. Flag the discrepancy.
- ❌ **Not found** — no matching paper in the database. Flag as requiring manual verification.

For each citation, assess plausibility based on:
1. Venue reputation — is the venue appropriate for the claim?
2. Citation count — do the numbers seem reasonable for this venue/year?
3. Author match — do the authors match the research area?
4. Field alignment — is this paper in the expected field of study?

Format as a structured Markdown report with a SUMMARY table at the top.

--- Database Verification Results ---
{db_results}

--- Original Citations to Review ---
{citations}"""


@router.post("/projects/{project_id}/verify-citations", status_code=status.HTTP_202_ACCEPTED)
async def verify_citations(
    project_id: str,
    body: CitationVerificationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Verify citations against the Semantic Scholar database, then analyze with the research agent."""
    project = get_project(get_db_path(), project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Query Semantic Scholar database first
    from ...s2.queries import verify_citations as s2_verify

    s2_results = s2_verify(body.citations)
    db_context = _format_s2_results(s2_results)

    prompt = _CITATION_PROMPT.format(db_results=db_context, citations=body.citations)
    run_id = f"citation-{project_id}-{time.time():.0f}"
    workspace_dir = str(RUNS_DIR / "research" / run_id)

    # If S2 DB is available, save the raw results too
    if s2_results.get("available"):
        raw_results = json.dumps(s2_results, indent=2, default=str)
    else:
        raw_results = "Semantic Scholar database not available. Using AI-only analysis."

    background_tasks.add_task(
        _save_citation_output, project_id, current_user.id, run_id, prompt, workspace_dir, raw_results,
    )

    status_msg = (
        f"Found {s2_results.get('verified', 0)}/{s2_results.get('total_citations', 0)} citations in database. "
        f"Analysis in progress."
    ) if s2_results.get("available") else "Semantic Scholar DB not configured. Using AI-only analysis. Set S2_DB_PATH env var."

    return {"status": "generating", "message": status_msg}


def _format_s2_results(s2_results: dict) -> str:
    """Format S2 database results into a readable context string."""
    if not s2_results.get("available"):
        return "Semantic Scholar database is not configured."

    lines = [
        f"Total citations parsed: {s2_results.get('total_citations', 0)}",
        f"Verified in database: {s2_results.get('verified', 0)}",
        f"Not found: {s2_results.get('not_found', 0)}",
        f"Suspicious: {s2_results.get('suspicious', 0)}",
        "",
    ]

    for result in s2_results.get("results", []):
        lines.append("---")
        lines.append(f"Raw text: {result['raw_text'][:200]}")
        lines.append(f"Status: {result['status']}")
        if result.get("flags"):
            for flag in result["flags"]:
                lines.append(f"Flag: {flag}")
        for match in result.get("matches", []):
            lines.append(f"  Matched: {match.get('title', '?')} ({match.get('year', '?')})")
            lines.append(f"  Venue: {match.get('venue', '?')}")
            lines.append(f"  Citations: {match.get('citation_count', '?')}")
            lines.append(f"  Authors: {', '.join(match.get('authors', [])[:3])}")
            lines.append(f"  DOI: {match.get('doi', 'N/A')}")
            lines.append(f"  Fields: {', '.join(match.get('fields_of_study', [])[:3])}")
        lines.append("")

    return "\n".join(lines)


async def _save_citation_output(project_id: str, user_id: str, run_id: str, prompt: str, workspace_dir: str, raw_results: str = "") -> None:
    text = await _run_agent_and_get_output(
        run_id, prompt, workspace_dir, agent_type="research",
        context=UsageContext(task="verify-citations", user_id=user_id, project_id=project_id),
    )
    if text:
        db = get_db_path()
        exp = create_experiment(db, project_id=project_id, name="Citation Review", created_by=user_id)
        # Save AI analysis as the main entry
        create_entry(db, experiment_id=exp.id, entry_type="result", title="Citation Verification Report — AI Analysis", body=text, author_id=user_id)
        # Save raw DB results as a note
        if raw_results:
            create_entry(db, experiment_id=exp.id, entry_type="note", title="Raw Database Results", body=raw_results, author_id=user_id)
