"""Shared helper functions for AI paper drafting."""

from __future__ import annotations

from ...crud.experiment_entries import list_entries
from ...crud.experiments import list_experiments, list_linked_tasks
from ...crud.projects import get_project
from ...crud.tasks import list_tasks
from ...db import get_db_path


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

Use only the information provided. Where details are missing, note them in **[brackets]**. Do not fabricate data or citations.

---
{context}
---"""
