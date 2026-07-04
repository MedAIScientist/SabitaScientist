"""AI paper drafting — collect experiment data, dispatch writing agent, create publication."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from ...crud.experiment_entries import list_entries
from ...crud.experiments import list_experiments, list_linked_tasks
from ...crud.projects import get_project
from ...crud.publications import create_publication
from ...crud.tasks import list_tasks
from ...db import get_db_path
from ...models import User
from ..deps import require_project_role

router = APIRouter()
RUNNER_URL = os.getenv("RUNNER_URL", "http://127.0.0.1:8001")


def _build_project_context(project_id: str) -> str:
    """Assemble full project context: project info, tasks, experiments + entries."""
    db = get_db_path()
    project = get_project(db, project_id)
    if not project:
        return "Project not found."

    tasks = list_tasks(db, project_id)
    experiments = list_experiments(db, project_id)

    sections = [
        f"# Project: {project.name}",
        f"Description: {project.description or '(none)'}",
    ]

    if tasks:
        sections.append("\n## Tasks")
        for t in tasks:
            sections.append(f"- [{t.status}] {t.title} (priority: {t.priority})")

    if experiments:
        sections.append("\n## Experiments")
        for exp in experiments:
            entries = list_entries(db, exp.id)
            linked = list_linked_tasks(db, exp.id)
            sections.append(f"\n### {exp.name} (status: {exp.status})")
            if exp.hypothesis:
                sections.append(f"Hypothesis: {exp.hypothesis}")
            if exp.protocol:
                sections.append(f"Protocol: {exp.protocol}")
            if linked:
                sections.append(f"Linked tasks: {', '.join(t.title for t in linked)}")
            if entries:
                for e in entries:
                    body_preview = (e.body or "")[:500]
                    sections.append(f"\n#### {e.title} ({e.type})")
                    sections.append(body_preview)

    return "\n".join(sections)


def _build_draft_prompt(context: str) -> str:
    return f"""You are a scientific paper writing assistant. Based on the project data below, draft a complete research paper in Markdown.

Structure the paper with:
1. **Title** — A concise, descriptive title
2. **Abstract** — 150-250 word summary
3. **Introduction** — Background, gap, and objective
4. **Methods** — Experimental procedures
5. **Results** — Key findings from experiment entries
6. **Discussion** — Interpretation and significance
7. **Conclusion**

Use only the information provided. Where details are missing, note them in brackets. Do not fabricate data or citations.

---
{context}
---"""


@router.post(
    "/projects/{project_id}/draft-paper",
    status_code=status.HTTP_202_ACCEPTED,
)
async def draft_paper_from_project(
    project_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Collect project experiment data and dispatch the writing agent to draft a paper."""
    context = _build_project_context(project_id)
    if context == "Project not found.":
        raise HTTPException(status_code=404, detail="Project not found")

    prompt = _build_draft_prompt(context)

    # Create a draft publication immediately
    db = get_db_path()
    project = get_project(db, project_id)
    pub = create_publication(
        db,
        title=f"Draft: {project.name} — AI Generated",
        created_by=current_user.id,
        project_id=project_id,
        venue_type="preprint",
        abstract="AI-generated draft (in progress).",
    )

    workspace_base = os.getenv(
        "EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs")
    )
    workspace_dir = str(Path(workspace_base) / "drafts" / pub.id)

    background_tasks.add_task(_run_draft_agent, pub.id, prompt, workspace_dir)

    return {
        "publication_id": pub.id,
        "status": "drafting",
        "message": f"Paper draft started — publication {pub.id} created",
    }


async def _run_draft_agent(pub_id: str, prompt: str, workspace_dir: str) -> None:
    """Run the writing agent and save the output as the publication abstract."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(
                f"{RUNNER_URL}/runs",
                json={
                    "run_id": f"draft-{pub_id}",
                    "agent_type": "writing",
                    "prompt": prompt,
                    "workspace_dir": workspace_dir,
                },
            )
            if resp.status_code != 200:
                return

            accumulated: list[str] = []
            async with client.stream(
                "GET", f"{RUNNER_URL}/runs/draft-{pub_id}/stream"
            ) as stream:
                async for line in stream.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            if event.get("type") == "token":
                                accumulated.append(event["data"])
                            elif event.get("type") == "error":
                                return
                        except Exception:
                            pass

            draft_text = "".join(accumulated)
            if draft_text:
                from ...crud.publications import update_publication
                db = get_db_path()
                # Extract first 500 chars as abstract, store full in details
                abstract = draft_text[:500].strip()
                update_publication(
                    db, pub_id,
                    abstract=abstract,
                    status="draft",
                )
    except Exception:
        pass
