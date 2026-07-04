"""AI-powered research tools — grant writer, figure generator, impact dashboard."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from ...crud.experiment_entries import create_entry, list_entries
from ...crud.experiments import get_experiment, list_linked_tasks
from ...crud.projects import get_project
from ...crud.publications import list_publications
from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import GrantWriterRequest

router = APIRouter()
RUNNER_URL = os.getenv("RUNNER_URL", "http://127.0.0.1:8001")

# =============================================================================
# AI Grant Writer
# =============================================================================

_GRANT_TEMPLATES = {
    "nih_r01": "NIH R01 — Research Project Grant. 12-page limit, Specific Aims page, Research Strategy (Significance, Innovation, Approach).",
    "nsf": "NSF Standard Grant. 15-page project description, Intellectual Merit + Broader Impacts required.",
    "erc": "ERC Starting/Consolidator/Advanced Grant. Extended narrative with ground-breaking ambition, no page limit but concise.",
    "wellcome": "Wellcome Trust Grant. Focus on transformative research, public engagement, and researcher development.",
    "general": "General Research Grant. Standard structure: Abstract, Background, Aims, Methods, Timeline, Budget, References.",
}

_GRANT_WRITER_PROMPT = """You are an expert grant proposal writer. Draft a complete grant proposal based on the project context below.

**Grant Type**: {grant_type} ({grant_description})

**Structure the proposal with these sections:**

1. **Title** — Catchy, descriptive title for the proposal
2. **Abstract** — 250-300 word summary accessible to non-specialist reviewers
3. **Background & Significance** — Current state of knowledge, gap this proposal addresses, why it matters
4. **Innovation** — What is novel about this approach? How does it differ from existing work?
5. **Specific Aims / Objectives** — 2-4 clear, measurable aims
6. **Research Strategy** — For each aim:
   - Approach and rationale
   - Experimental design and methods
   - Expected outcomes
   - Alternative strategies and contingency plans
7. **Timeline** — Gantt-style timeline (12-60 months)
8. **Budget Justification** — Key personnel, equipment, supplies, travel
9. **References** — Key citations supporting the proposal

**Writing guidelines:**
- Be specific and concrete — avoid vague promises
- Reference preliminary data from the project context where available
- Address potential pitfalls and alternatives
- Use professional academic language
- Stay within the page/concept limits of the grant type
- Do not fabricate data or citations

--- Project Context ---
{context}"""


@router.post("/projects/{project_id}/grant-proposal", status_code=status.HTTP_202_ACCEPTED)
async def draft_grant_proposal(
    project_id: str,
    body: GrantWriterRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Draft a grant proposal using the writing agent, templated for specific funders."""
    project = get_project(get_db_path(), project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    context = _build_project_context(project_id)
    grant_desc = _GRANT_TEMPLATES.get(body.grant_type, _GRANT_TEMPLATES["general"])
    prompt = _GRANT_WRITER_PROMPT.format(
        grant_type=body.grant_type.upper(),
        grant_description=grant_desc,
        context=context,
    )

    pub_title = f"Grant Proposal: {body.grant_type.upper()} — {project.name}"
    from ...crud.publications import create_publication
    pub = create_publication(
        get_db_path(), title=pub_title, created_by=current_user.id,
        project_id=project_id, venue_type="other",
        abstract=f"AI-generated {body.grant_type} grant proposal (in progress).",
    )

    run_id = f"grant-{pub.id}-{__import__('time').time():.0f}"
    workspace_base = os.getenv("EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs"))
    workspace_dir = str(Path(workspace_base) / "grants" / run_id)

    background_tasks.add_task(_run_grant_writer, pub.id, run_id, prompt, workspace_dir)
    return {"status": "drafting", "publication_id": pub.id, "grant_type": body.grant_type}


async def _run_grant_writer(pub_id: str, run_id: str, prompt: str, workspace_dir: str) -> None:
    from ...crud.publications import update_publication as _up
    text = await _run_agent(run_id, prompt, workspace_dir, agent_type="writing")
    if text:
        _up(get_db_path(), pub_id, abstract=text[:800].strip(), status="draft")


# =============================================================================
# Auto Figure Generator
# =============================================================================

_FIGURE_GEN_PROMPT = """You are a data analysis agent. Your task is to analyze the experiment data below and produce publication-quality analysis.

For each dataset or result, generate:

1. **Data Summary** — Key statistics (mean, std, n, effect sizes where applicable)
2. **Analysis Code** — Python code using matplotlib/seaborn to create figures. Write clean, self-contained code.
3. **Figure Description** — What each figure shows and how to interpret it
4. **Statistical Tests** — Appropriate tests with results

Important guidelines:
- Write matplotlib/seaborn code that can be executed directly
- Save figures as PNG files
- Include axis labels, titles, and legends
- Use publication-ready styling (appropriate font sizes, color schemes)
- Include effect sizes and confidence intervals where appropriate
- The code will be saved alongside the analysis

--- Experiment Data ---
{context}"""


@router.post("/projects/{project_id}/experiments/{exp_id}/generate-figures", status_code=status.HTTP_202_ACCEPTED)
async def generate_figures(
    project_id: str,
    exp_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Generate publication-quality figures from experiment data using the data-analysis agent."""
    db = get_db_path()
    exp = get_experiment(db, exp_id)
    if not exp or exp.project_id != project_id:
        raise HTTPException(404, "Experiment not found")

    entries = list_entries(db, exp_id)
    linked = list_linked_tasks(db, exp_id)
    parts = [
        f"# Experiment: {exp.name}",
        f"Hypothesis: {exp.hypothesis or 'not set'}",
        f"Protocol: {exp.protocol or 'not set'}",
    ]
    if linked:
        parts.append(f"Linked tasks: {', '.join(t.title for t in linked)}")
    if entries:
        for e in entries:
            parts.append(f"\n## {e.title} ({e.type})")
            parts.append(e.body or "")

    prompt = _FIGURE_GEN_PROMPT.format(context="\n".join(parts))
    run_id = f"figures-{exp_id}-{__import__('time').time():.0f}"
    workspace_base = os.getenv("EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs"))
    workspace_dir = str(Path(workspace_base) / "figures" / run_id)

    background_tasks.add_task(_run_figure_generator, exp_id, current_user.id, run_id, prompt, workspace_dir)
    return {"status": "generating", "experiment_id": exp_id}


async def _run_figure_generator(exp_id: str, user_id: str, run_id: str, prompt: str, workspace_dir: str) -> None:
    text = await _run_agent(run_id, prompt, workspace_dir, agent_type="data_analysis")
    if text:
        db = get_db_path()
        create_entry(db, experiment_id=exp_id, type="result",
                     title="AI-Generated Figures & Analysis",
                     body=text, author_id=user_id)


# =============================================================================
# Research Impact Dashboard
# =============================================================================

_IMPACT_QUERY = """With the research context below, generate a structured impact analysis report.

For each publication in the context, analyze:
1. **Citation Impact** — Total citations, influential citations, citation velocity (citations/year)
2. **Field Percentile** — Estimated percentile ranking based on citation count
3. **Collaboration Network** — Co-authors, institutions, cross-disciplinary links
4. **Trend Analysis** — Is this research area growing? Declining? Stable?
5. **Funding Impact** — Estimated grant success probability based on publication record

Format as a structured Markdown report with:
- Executive summary of overall impact
- Per-publication breakdown
- Trend visualizations (described in text)
- Recommendations for improving impact

--- Research Context ---
{context}"""


@router.get("/labs/{lab_id}/research-impact")
async def research_impact(
    lab_id: str,
    current_user: User = Depends(get_current_user),
):
    """Generate a research impact report for a lab using S2 data and publication records."""
    from ...crud.labs import get_lab as _get_lab
    from ...crud.labs import list_members as _list_members
    db = get_db_path()
    lab = _get_lab(db, lab_id)
    if not lab:
        raise HTTPException(404, "Lab not found")

    # Get all projects for this lab
    with get_db(db) as conn:
        project_ids = [r["id"] for r in conn.execute(
            "SELECT id FROM projects WHERE lab_id = ? AND archived_at IS NULL", (lab_id,)
        ).fetchall()]

    pubs = []
    for pid in project_ids:
        pubs.extend(list_publications(db, project_id=pid))

    # Try S2 data for citation counts
    s2_data = []
    from ...s2.queries import is_available, search_by_doi, search_by_title
    if is_available():
        for p in pubs:
            if p.doi:
                paper = search_by_doi(p.doi)
            else:
                matches = search_by_title(p.title, limit=1)
                paper = matches[0] if matches else None
            if paper:
                s2_data.append({
                    "title": p.title,
                    "status": p.status,
                    "citations": paper.citation_count,
                    "influential_citations": paper.influential_citation_count,
                    "venue": paper.venue or p.venue,
                    "year": paper.year,
                    "fields": paper.fields_of_study,
                    "is_open_access": paper.is_open_access,
                })

    members = _list_members(db, lab_id)
    member_count = len(members)
    total_citations = sum(d.get("citations", 0) for d in s2_data) if s2_data else 0
    h_index = _compute_h_index([d.get("citations", 0) for d in s2_data]) if s2_data else 0

    return {
        "lab_id": lab_id,
        "lab_name": lab.name,
        "total_publications": len(pubs),
        "s2_matched": len(s2_data),
        "total_citations": total_citations,
        "h_index": h_index,
        "average_citations_per_paper": round(total_citations / max(len(s2_data), 1), 1),
        "member_count": member_count,
        "publications_by_status": {s: sum(1 for p in pubs if p.status == s) for s in {p.status for p in pubs}},
        "publications": s2_data,
        "members": [{"user_id": m.user_id, "role": m.role} for m in members],
    }


def _compute_h_index(citation_counts: list[int]) -> int:
    sorted_citations = sorted(citation_counts, reverse=True)
    h = 0
    for i, c in enumerate(sorted_citations, 1):
        if c >= i:
            h = i
        else:
            break
    return h


# =============================================================================
# Helpers
# =============================================================================

def _build_project_context(project_id: str) -> str:
    from .drafting_helpers import _build_project_context as _ctx
    return _ctx(project_id)


async def _run_agent(run_id: str, prompt: str, workspace_dir: str, agent_type: str = "writing") -> str | None:
    from .drafting import _run_agent_and_get_output
    return await _run_agent_and_get_output(run_id, prompt, workspace_dir, agent_type)
