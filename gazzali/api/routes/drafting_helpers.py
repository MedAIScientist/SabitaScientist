"""Shared helper functions for AI paper drafting."""

from __future__ import annotations

import hashlib

from ...crud.experiment_entries import list_entries
from ...crud.experiment_metrics import list_metrics
from ...crud.experiments import list_experiments, list_linked_tasks
from ...crud.projects import get_project
from ...crud.tasks import list_tasks
from ...db import get_db_path


def prompt_fingerprint(prompt: str) -> str:
    """Short digest of the prompt that produced a draft.

    Stored instead of the prompt itself: prompts embed project data, and a
    disclosure record should identify a generation without copying its inputs.
    """
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


GROUNDING_RULE = """
--- Data grounding rules (mandatory) ---
Every number you write MUST appear verbatim in a "Recorded metrics" table above.
Do not compute, estimate, round, average, interpolate, or otherwise derive any
numeric value that is not in those tables. Prose notes are context only — they
are NOT a source of numbers.

If a section would normally report a number that is not in the tables, write
[TBD: not recorded] instead of a number.
Do not claim statistical significance, effect sizes, or confidence intervals
unless a p-value, effect size, or interval appears in the tables.
Do not invent citations.
"""


def render_metrics_block(experiment_id: str) -> str:
    """Markdown table of recorded metrics, or an explicit 'none' marker.

    The 'none' case is stated loudly on purpose: an empty section reads as an
    invitation to invent, whereas an explicit "no numbers recorded" does not.
    """
    metrics = list_metrics(get_db_path(), experiment_id)
    if not metrics:
        return (
            "\n**Recorded metrics: NONE.** No numeric results have been recorded "
            "for this experiment. Report no numbers for it.\n"
        )
    lines = [
        "\n#### Recorded metrics (the only numbers you may report)",
        "| metric | value | unit | split | n | stderr |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for m in metrics:
        lines.append(
            f"| {m.name} | {m.value:g} | {m.unit or ''} | {m.split or ''} "
            f"| {'' if m.n is None else m.n} "
            f"| {'' if m.stderr is None else format(m.stderr, 'g')} |"
        )
    return "\n".join(lines) + "\n"


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
            sections.append(render_metrics_block(exp.id))
            if entries:
                for e in entries:
                    sections.append(f"\n#### {e.title} ({e.type})")
                    sections.append(_entry_body(e))

    return "\n".join(sections)


def _entry_body(entry) -> str:
    """Entry text for prompts. Results are never truncated.

    Notes are prose context and can be clipped; a result entry may carry the
    only description of what was measured, so clipping it invites the model to
    fill the gap itself.
    """
    body = entry.body or ""
    if entry.type == "result":
        return body
    return body[:500] + ("\n[note truncated]" if len(body) > 500 else "")


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
---
{GROUNDING_RULE}"""
