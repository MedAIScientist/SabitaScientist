"""Project Research Corpus → paper context assembler.

Builds a versioned evidence pack for paper writing from **all** project
sources. Every fact carries a source id so later stages can bind claims to
evidence and integrity checks can verify numbers.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .db import get_db

# Source kinds used in evidence_ids
#   project:{id}  phase:{id}  task:{id}  exp:{id}  metric:{id}  entry:{id}
#   wiki:{id}  grant:{id}  irb:{id}  dataset:{id}  ref:{id}  weekly:{id}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def build_paper_context(
    db_path: Path,
    project_id: str | None,
    publication_id: str | None = None,
    *,
    include: dict | None = None,
    max_task_comments: int = 3,
    max_weekly: int = 20,
) -> dict:
    """Assemble a structured ContextPack for paper drafting.

    Returns a JSON-serializable dict:
      {
        "meta": {...},
        "sources": {kind: [ {id, label, text, ...} ]},
        "summary": {counts, warnings},
        "text": "markdown prompt block",
        "evidence_ids": ["exp:…", "metric:…", ...]
      }
    """
    include = include or {}
    default_on = {
        "project": True,
        "phases": True,
        "tasks": True,
        "experiments": True,
        "wiki": True,
        "literature": True,
        "funding": True,
        "ethics": True,
        "data": True,
        "weekly": True,
        "open_questions": True,
    }
    flags = {**default_on, **include}

    sources: dict[str, list[dict]] = {
        "project": [],
        "phases": [],
        "tasks": [],
        "experiments": [],
        "literature": [],
        "wiki": [],
        "funding": [],
        "ethics": [],
        "data": [],
        "weekly": [],
        "open_questions": [],
    }
    evidence_ids: list[str] = []

    def _add(kind: str, rec: dict, eid: str | None = None) -> None:
        sources[kind].append(rec)
        if eid:
            evidence_ids.append(eid)

    with get_db(db_path) as conn:
        project = None
        if project_id:
            project = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()

        if project and flags["project"]:
            _add(
                "project",
                {
                    "id": f"project:{project['id']}",
                    "label": project["name"],
                    "text": project["description"] or "",
                },
                f"project:{project['id']}",
            )

        # Publication target (if any)
        pub = None
        if publication_id:
            pub = conn.execute(
                "SELECT * FROM publications WHERE id = ?", (publication_id,)
            ).fetchone()
            if pub and not project_id:
                project_id = pub["project_id"]

        # Phases (columns: name, color, position, target_date — no description/status)
        if project_id and flags["phases"]:
            for r in conn.execute(
                "SELECT * FROM project_phases WHERE project_id = ? ORDER BY position, name",
                (project_id,),
            ):
                target = r["target_date"]
                _add(
                    "phases",
                    {
                        "id": f"phase:{r['id']}",
                        "label": r["name"],
                        "text": f"target: {target}" if target else "",
                    },
                    f"phase:{r['id']}",
                )

        # Tasks + top comments
        if project_id and flags["tasks"]:
            for t in conn.execute(
                "SELECT * FROM tasks WHERE project_id = ? ORDER BY status, priority DESC LIMIT 80",
                (project_id,),
            ):
                comments = conn.execute(
                    "SELECT body FROM task_comments WHERE task_id = ? ORDER BY created_at DESC LIMIT ?",
                    (t["id"], max_task_comments),
                ).fetchall()
                comment_text = " | ".join(c["body"][:200] for c in comments if c["body"])
                text = f"[{t['status']}] {t['title']}"
                if t["description"]:
                    text += f" — {t['description'][:400]}"
                if comment_text:
                    text += f" | decisions: {comment_text}"
                _add(
                    "tasks",
                    {"id": f"task:{t['id']}", "label": t["title"], "text": text},
                    f"task:{t['id']}",
                )

        # Experiments + metrics + entries
        exp_ids: list[str] = []
        if project_id and flags["experiments"]:
            for exp in conn.execute(
                "SELECT * FROM experiments WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ):
                exp_ids.append(exp["id"])
                metrics = conn.execute(
                    "SELECT * FROM experiment_metrics WHERE experiment_id = ?",
                    (exp["id"],),
                ).fetchall()
                entries = conn.execute(
                    "SELECT * FROM experiment_entries WHERE experiment_id = ? ORDER BY created_at DESC LIMIT 30",
                    (exp["id"],),
                ).fetchall()
                parts = [f"status={exp['status']}"]
                if exp["hypothesis"]:
                    parts.append(f"hypothesis: {exp['hypothesis']}")
                if exp["protocol"]:
                    parts.append(f"protocol: {exp['protocol']}")
                metric_lines = []
                for m in metrics:
                    metric_lines.append(
                        f"{m['name']}={m['value']} {m['unit'] or ''}".strip()
                    )
                    _add_metric_evidence = f"metric:{m['id']}"
                    evidence_ids.append(_add_metric_evidence)
                if metric_lines:
                    parts.append("metrics: " + "; ".join(metric_lines))
                result_bodies = []
                for e in entries:
                    body = e["body"] or ""
                    if e["type"] == "result":
                        result_bodies.append(f"{e['title']}: {body}")
                    evidence_ids.append(f"entry:{e['id']}")
                if result_bodies:
                    parts.append("results: " + " || ".join(result_bodies[:8]))
                _add(
                    "experiments",
                    {
                        "id": f"exp:{exp['id']}",
                        "label": exp["name"],
                        "text": "\n".join(parts),
                        "metrics": [
                            {
                                "id": f"metric:{m['id']}",
                                "name": m["name"],
                                "value": m["value"],
                                "unit": m["unit"],
                            }
                            for m in metrics
                        ],
                    },
                    f"exp:{exp['id']}",
                )

        # Literature = other publications in the project (and the target itself's refs if abstract mentions)
        if project_id and flags["literature"]:
            for p in conn.execute(
                """SELECT id, title, venue, venue_type, status, doi, abstract FROM publications
                   WHERE project_id = ? ORDER BY created_at DESC LIMIT 40""",
                (project_id,),
            ):
                if publication_id and p["id"] == publication_id:
                    continue
                text = f"{p['venue_type'] or 'work'} · {p['status']}"
                if p["venue"]:
                    text += f" · {p['venue']}"
                if p["doi"]:
                    text += f" · doi:{p['doi']}"
                if p["abstract"]:
                    text += f" — {p['abstract'][:280]}"
                _add(
                    "literature",
                    {"id": f"ref:{p['id']}", "label": p["title"], "text": text},
                    f"ref:{p['id']}",
                )

        # Lab wiki (if project has a lab) — column is `content`, not `body`
        if project_id and flags["wiki"] and project and project["lab_id"]:
            for w in conn.execute(
                """SELECT id, title, content FROM lab_wiki_pages
                   WHERE lab_id = ? ORDER BY updated_at DESC LIMIT 15""",
                (project["lab_id"],),
            ):
                _add(
                    "wiki",
                    {
                        "id": f"wiki:{w['id']}",
                        "label": w["title"],
                        "text": (w["content"] or "")[:800],
                    },
                    f"wiki:{w['id']}",
                )

        # Funding (grants linked to project)
        if project_id and flags["funding"]:
            for g in conn.execute(
                "SELECT id, title, funder, status FROM grants WHERE project_id = ? LIMIT 20",
                (project_id,),
            ):
                _add(
                    "funding",
                    {
                        "id": f"grant:{g['id']}",
                        "label": f"{g['funder']} — {g['title']}",
                        "text": f"status={g['status']}",
                    },
                    f"grant:{g['id']}",
                )

        # Ethics
        if project_id and flags["ethics"]:
            for r in conn.execute(
                "SELECT id, protocol_number, status, title, approval_date FROM irb_approvals WHERE project_id = ? LIMIT 10",
                (project_id,),
            ):
                _add(
                    "ethics",
                    {
                        "id": f"irb:{r['id']}",
                        "label": r["protocol_number"] or r["title"] or "IRB",
                        "text": f"status={r['status']} approval_date={r['approval_date'] or 'n/a'}",
                    },
                    f"irb:{r['id']}",
                )

        # Datasets (lab-scoped)
        if flags["data"]:
            lab_id = project["lab_id"] if project else None
            if lab_id:
                for d in conn.execute(
                    """SELECT id, name, purpose, status, modality FROM datasets
                       WHERE lab_id = ? LIMIT 20""",
                    (lab_id,),
                ):
                    _add(
                        "data",
                        {
                            "id": f"dataset:{d['id']}",
                            "label": d["name"],
                            "text": f"{d['purpose'] or ''} modality={d['modality'] or 'n/a'} status={d['status']}",
                        },
                        f"dataset:{d['id']}",
                    )

        # Weekly narrative + open questions
        if project_id and flags.get("weekly", True):
            rows = conn.execute(
                """SELECT i.id, i.item_title, i.what_changed, i.next_step,
                          i.needs_help, i.blocker, i.progress_pct, r.week_start
                   FROM weekly_report_items i
                   JOIN weekly_reports r ON r.id = i.report_id
                   WHERE r.status = 'submitted'
                   ORDER BY r.week_start DESC LIMIT ?""",
                (max_weekly,),
            ).fetchall()
            for r in rows:
                text = (
                    f"[{r['week_start']}] {r['item_title']} — {r['what_changed'] or ''}"
                    f" next: {r['next_step'] or ''} ({r['progress_pct']}%)"
                )
                _add("weekly", {"id": f"weekly:{r['id']}", "label": r["item_title"], "text": text})
                evidence_ids.append(f"weekly:{r['id']}")
                if r["needs_help"] and flags.get("open_questions", True):
                    _add(
                        "open_questions",
                        {
                            "id": f"weekly:{r['id']}",
                            "label": r["item_title"],
                            "text": r["blocker"] or r["what_changed"] or "help needed",
                        },
                    )

    # Warnings
    warnings: list[str] = []
    if not sources["experiments"]:
        warnings.append("No experiments — Results/Metrics will lack verified numbers.")
    if not any(e.get("metrics") for e in sources["experiments"]):
        warnings.append("No experiment metrics — do not invent numeric results.")
    if not sources["literature"]:
        warnings.append("No bibliography / related publications for Related Work.")
    if not sources["ethics"]:
        warnings.append("No IRB record — ethics statement cannot be auto-checked.")
    if not sources["funding"]:
        warnings.append("No grants — funding statement must be written manually.")

    text = render_context_text(sources, pub)
    summary = {
        "counts": {k: len(v) for k, v in sources.items()},
        "warnings": warnings,
        "experiment_ids": exp_ids,
        "metric_count": sum(len(e.get("metrics") or []) for e in sources["experiments"]),
    }

    return {
        "meta": {
            "project_id": project_id,
            "publication_id": publication_id,
            "project_name": project["name"] if project else None,
            "publication_title": pub["title"] if pub else None,
            "built_at": _now(),
        },
        "sources": sources,
        "summary": summary,
        "text": text,
        "evidence_ids": sorted(set(evidence_ids)),
    }


def render_context_text(sources: dict[str, list[dict]], pub=None) -> str:
    """Render the ContextPack as a markdown prompt block."""
    parts: list[str] = ["# Project Research Corpus"]
    if pub:
        parts.append(f"\n## Target paper\n{pub['title']} ({pub['venue_type']}, {pub['status']})")

    section_titles = {
        "project": "Project",
        "phases": "Phases",
        "tasks": "Tasks & decisions",
        "experiments": "Experimental evidence (use ONLY these numbers)",
        "literature": "Related work / prior outputs",
        "wiki": "Lab notes",
        "funding": "Funding",
        "ethics": "Ethics",
        "data": "Data",
        "weekly": "Progress timeline",
        "open_questions": "Open questions",
    }
    for kind, title in section_titles.items():
        rows = sources.get(kind) or []
        if not rows:
            continue
        parts.append(f"\n## {title}")
        for r in rows:
            parts.append(f"\n### [{r['id']}] {r['label']}")
            parts.append(r.get("text") or "")
    return "\n".join(parts)


# ── Snapshots ────────────────────────────────────────────────────────────────


def save_context_snapshot(
    db_path: Path,
    pack: dict,
    created_by: str,
    label: str | None = None,
) -> dict:
    """Persist a ContextPack so later drafts are reproducible."""
    sid = _new_id()
    now = _now()
    payload = json.dumps(pack, ensure_ascii=False)
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO paper_context_snapshots
               (id, project_id, publication_id, payload_json, label, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sid,
                pack.get("meta", {}).get("project_id"),
                pack.get("meta", {}).get("publication_id"),
                payload,
                label,
                created_by,
                now,
            ),
        )
    return {
        "id": sid,
        "label": label,
        "created_at": now,
        "summary": pack.get("summary"),
        "meta": pack.get("meta"),
    }


def get_context_snapshot(db_path: Path, snapshot_id: str) -> dict | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM paper_context_snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
    if not row:
        return None
    pack = json.loads(row["payload_json"])
    return {
        "id": row["id"],
        "label": row["label"],
        "created_at": row["created_at"],
        "created_by": row["created_by"],
        "pack": pack,
    }


def list_context_snapshots(db_path: Path, publication_id: str) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT id, label, created_at, created_by FROM paper_context_snapshots
               WHERE publication_id = ? ORDER BY created_at DESC LIMIT 20""",
            (publication_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Claim map (outline) ──────────────────────────────────────────────────────


def replace_claim_map(db_path: Path, publication_id: str, claims: list[dict]) -> list[dict]:
    """Replace the outline/claim map for a paper."""
    now = _now()
    out: list[dict] = []
    with get_db(db_path) as conn:
        conn.execute(
            "DELETE FROM paper_claim_map WHERE publication_id = ?", (publication_id,)
        )
        for i, c in enumerate(claims):
            cid = _new_id()
            evidence_ids = c.get("evidence_ids") or []
            conn.execute(
                """INSERT INTO paper_claim_map
                   (id, publication_id, section, claim_text, evidence_ids, sort_order, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cid,
                    publication_id,
                    c.get("section") or "general",
                    c.get("claim_text") or "",
                    json.dumps(evidence_ids),
                    i,
                    c.get("status") or "planned",
                    now,
                ),
            )
            out.append(
                {
                    "id": cid,
                    "section": c.get("section") or "general",
                    "claim_text": c.get("claim_text") or "",
                    "evidence_ids": evidence_ids,
                    "sort_order": i,
                    "status": c.get("status") or "planned",
                }
            )
    return out


def list_claim_map(db_path: Path, publication_id: str) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM paper_claim_map WHERE publication_id = ?
               ORDER BY sort_order, section""",
            (publication_id,),
        ).fetchall()
    result = []
    for r in rows:
        result.append(
            {
                "id": r["id"],
                "section": r["section"],
                "claim_text": r["claim_text"],
                "evidence_ids": json.loads(r["evidence_ids"] or "[]"),
                "sort_order": r["sort_order"],
                "status": r["status"],
            }
        )
    return result


# ── Integrity runs ───────────────────────────────────────────────────────────


def save_integrity_run(
    db_path: Path, publication_id: str, checks: list[dict], passed: bool
) -> dict:
    rid = _new_id()
    now = _now()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO paper_integrity_runs
               (id, publication_id, checks_json, passed, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (rid, publication_id, json.dumps(checks), int(passed), now),
        )
    return {"id": rid, "passed": passed, "checks": checks, "created_at": now}
