"""Paper pipeline API — context pack, outline, staged drafts, integrity, review points."""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from ... import paper_context
from ...crud.publications import create_version, get_publication, list_versions
from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user

router = APIRouter()

SECTIONS = ["abstract", "introduction", "related work", "methods", "results", "discussion", "conclusion"]


# ── Schemas ──────────────────────────────────────────────────────────────────


class ContextRequest(BaseModel):
    include: dict | None = None
    label: str | None = None
    snapshot: bool = False


class OutlineClaim(BaseModel):
    section: str = "general"
    claim_text: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    status: str = "planned"


class OutlineRequest(BaseModel):
    claims: list[OutlineClaim]


class SectionDraftRequest(BaseModel):
    section: str = "introduction"
    style: str = "academic"
    snapshot_id: str | None = None
    extra_instructions: str | None = None


# ── Context pack ─────────────────────────────────────────────────────────────


@router.post("/publications/{pub_id}/context")
def build_context(
    pub_id: str,
    body: ContextRequest | None = None,
    current_user: User = Depends(get_current_user),
):
    """Build (and optionally snapshot) the Project Research Corpus for this paper."""
    body = body or ContextRequest()
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    pack = paper_context.build_paper_context(
        db, pub.project_id, pub_id, include=body.include
    )
    snapshot = None
    if body.snapshot:
        snapshot = paper_context.save_context_snapshot(
            db, pack, current_user.id, body.label
        )
    return {
        "publication_id": pub_id,
        "snapshot": snapshot,
        "summary": pack["summary"],
        "meta": pack["meta"],
        "sources": {
            k: [{"id": r["id"], "label": r["label"]} for r in v]
            for k, v in pack["sources"].items()
        },
        "evidence_ids": pack["evidence_ids"],
        "text_length": len(pack["text"]),
    }


@router.get("/publications/{pub_id}/context")
def get_context_summary(
    pub_id: str, current_user: User = Depends(get_current_user)
):
    """Latest context summary + snapshots list (UI evidence panel)."""
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    pack = paper_context.build_paper_context(db, pub.project_id, pub_id)
    return {
        "publication_id": pub_id,
        "summary": pack["summary"],
        "meta": pack["meta"],
        "sources": {
            k: [{"id": r["id"], "label": r["label"]} for r in v]
            for k, v in pack["sources"].items()
        },
        "snapshots": paper_context.list_context_snapshots(db, pub_id),
    }


@router.get("/publications/{pub_id}/context/{snapshot_id}")
def get_snapshot(snapshot_id: str, current_user: User = Depends(get_current_user)):
    snap = paper_context.get_context_snapshot(get_db_path(), snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap


# ── Outline / claim map ──────────────────────────────────────────────────────


@router.put("/publications/{pub_id}/outline")
def put_outline(
    pub_id: str,
    body: OutlineRequest,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    if not get_publication(db, pub_id):
        raise HTTPException(status_code=404, detail="Publication not found")
    claims = [
        {
            "section": c.section,
            "claim_text": c.claim_text,
            "evidence_ids": c.evidence_ids,
            "status": c.status,
        }
        for c in body.claims
    ]
    return {"claims": paper_context.replace_claim_map(db, pub_id, claims)}


@router.get("/publications/{pub_id}/outline")
def get_outline(pub_id: str, current_user: User = Depends(get_current_user)):
    return {"claims": paper_context.list_claim_map(get_db_path(), pub_id)}


@router.post("/publications/{pub_id}/outline/generate")
def generate_outline(
    pub_id: str,
    background_tasks: BackgroundTasks,
    snapshot_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    """AI outline: section bullets bound to evidence ids (Stage 2)."""

    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    if snapshot_id:
        snap = paper_context.get_context_snapshot(db, snapshot_id)
        if not snap:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        pack = snap["pack"]
    else:
        pack = paper_context.build_paper_context(db, pub.project_id, pub_id)
        paper_context.save_context_snapshot(db, pack, current_user.id, "auto-outline")

    claims = _outline_from_pack(pack)
    paper_context.replace_claim_map(db, pub_id, claims)
    return {"claims": claims, "source": "ai"}


def _outline_from_pack(pack: dict) -> list[dict]:
    """Deterministic outline from the pack (no LLM required).

    Uses real evidence ids so the claim map is never empty of links.
    An LLM pass can refine wording later; structure comes from the corpus.
    """
    exps = pack["sources"].get("experiments") or []
    lit = pack["sources"].get("literature") or []
    funding = pack["sources"].get("funding") or []
    ethics = pack["sources"].get("ethics") or []
    data = pack["sources"].get("data") or []
    metrics = [m for e in exps for m in (e.get("metrics") or [])]

    claims: list[dict] = []

    claims.append(
        {
            "section": "abstract",
            "claim_text": "State problem, objective, key method, headline result, and contribution.",
            "evidence_ids": [e["id"] for e in exps[:2]] + [m["id"] for m in metrics[:3]],
        }
    )
    if lit:
        claims.append(
            {
                "section": "introduction",
                "claim_text": "Establish the gap relative to prior work and state contributions.",
                "evidence_ids": [r["id"] for r in lit[:3]],
            }
        )
    else:
        claims.append(
            {
                "section": "introduction",
                "claim_text": "State the problem and contributions (add bibliography for Related Work).",
                "evidence_ids": [e["id"] for e in exps[:1]],
            }
        )
    if lit:
        claims.append(
            {
                "section": "related work",
                "claim_text": "Compare against prior outputs/publications in this project.",
                "evidence_ids": [r["id"] for r in lit[:6]],
            }
        )
    methods_ids = [e["id"] for e in exps] + [d["id"] for d in data] + [r["id"] for r in ethics]
    claims.append(
        {
            "section": "methods",
            "claim_text": "Describe experimental design, data, and protocols reproducibly.",
            "evidence_ids": methods_ids,
        }
    )
    for e in exps[:6]:
        mids = [m["id"] for m in (e.get("metrics") or [])]
        claims.append(
            {
                "section": "results",
                "claim_text": f"Report verified metrics for: {e['label']}",
                "evidence_ids": [e["id"], *mids],
            }
        )
    if not exps:
        claims.append(
            {
                "section": "results",
                "claim_text": "No experiments linked — attach evidence before drafting Results.",
                "evidence_ids": [],
                "status": "blocked",
            }
        )
    claims.append(
        {
            "section": "discussion",
            "claim_text": "Interpret results, limitations, and relation to prior work.",
            "evidence_ids": [e["id"] for e in exps[:3]] + [r["id"] for r in lit[:2]],
        }
    )
    claims.append(
        {
            "section": "conclusion",
            "claim_text": "Summarize contribution and future work.",
            "evidence_ids": [e["id"] for e in exps[:1]],
        }
    )
    if funding:
        claims.append(
            {
                "section": "funding",
                "claim_text": "Declare funding sources.",
                "evidence_ids": [g["id"] for g in funding],
            }
        )
    return claims


# ── Section draft with evidence binding ──────────────────────────────────────


@router.post("/publications/{pub_id}/sections/draft")
def draft_section_staged(
    pub_id: str,
    body: SectionDraftRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Stage 3: draft one section from the claim map + context pack."""
    from ..routes.drafting import _build_publication_context, _build_section_prompt

    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    section = body.section.lower()
    claims = [
        c
        for c in paper_context.list_claim_map(db, pub_id)
        if c["section"].lower() == section or c["section"].lower() == "general"
    ]
    if not claims:
        # Fall back to a generated outline so the pipeline is usable immediately
        pack = paper_context.build_paper_context(db, pub.project_id, pub_id)
        all_claims = _outline_from_pack(pack)
        paper_context.replace_claim_map(db, pub_id, all_claims)
        claims = [c for c in all_claims if c["section"].lower() == section]

    evidence_ids: list[str] = []
    for c in claims:
        evidence_ids.extend(c.get("evidence_ids") or [])

    context = _build_publication_context(pub_id, section=section)
    claim_block = "\n".join(
        f"- ({c['section']}) {c['claim_text']} [evidence: {', '.join(c['evidence_ids']) or 'none'}]"
        for c in claims
    )
    extra = f"\n## Outline claims for this section\n{claim_block}\n"
    if body.extra_instructions:
        extra += f"\n## Author instructions\n{body.extra_instructions}\n"
    context = context + extra

    prompt = _build_section_prompt(context, section, body.style)
    create_version(
        db,
        pub_id,
        created_by=current_user.id,
        notes=f"AI staged draft: {section}",
        section=section,
        generated_by="ai-agent",
    )

    # Record evidence on the newest version row
    with get_db(db) as conn:
        conn.execute(
            """UPDATE publication_versions SET evidence_ids = ?, stage = 'section'
               WHERE id = (SELECT id FROM publication_versions
                           WHERE publication_id = ? ORDER BY version DESC LIMIT 1)""",
            (json.dumps(sorted(set(evidence_ids))), pub_id),
        )

    from .drafting import RUNS_DIR as _R
    from .drafting import _run_section_and_save

    workspace_dir = str(_R / "sections" / f"{pub_id}-{section}")
    run_id = f"section-{pub_id}-{section}"
    background_tasks.add_task(
        _run_section_and_save, pub_id, section, run_id, prompt, workspace_dir, current_user.id
    )
    return {
        "publication_id": pub_id,
        "section": section,
        "status": "drafting",
        "evidence_ids": sorted(set(evidence_ids)),
        "claim_count": len(claims),
    }


# ── Coherence pass ───────────────────────────────────────────────────────────


@router.post("/publications/{pub_id}/coherence")
def coherence_pass(
    pub_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Stage 4: cross-section consistency notes (does not rewrite Results)."""
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    versions = list_versions(db, pub_id)[:12]
    section_bits = []
    for v in versions:
        if v.content and v.section:
            section_bits.append(f"## {v.section}\n{v.content[:1500]}")
    claims = paper_context.list_claim_map(db, pub_id)
    claim_bits = "\n".join(f"- [{c['section']}] {c['claim_text']}" for c in claims)

    prompt = f"""You are a scientific editor. Review these manuscript sections for coherence.
Do NOT invent new results. Produce:
1. Consistency issues (contradictions, mismatched claims)
2. Abstract suggestions (if abstract missing/weak)
3. Gaps where a claim has no evidence

--- Claims ---
{claim_bits}

--- Sections ---
{chr(10).join(section_bits) if section_bits else '(no sections drafted yet)'}
"""
    from ...paths import RUNS_DIR
    from .drafting import _publication_context, _run_agent_and_get_output

    context = _publication_context(pub_id, current_user.id, "coherence")
    workspace_dir = str(RUNS_DIR / "coherence" / pub_id)

    async def _run():
        text = await _run_agent_and_get_output(
            f"coherence-{pub_id}", prompt, workspace_dir, "writing", context
        )
        if text:
            create_version(
                db,
                pub_id,
                created_by=current_user.id,
                notes="AI coherence pass",
                content=text,
                section="coherence",
                generated_by="ai-agent",
            )

    background_tasks.add_task(_run)
    return {"publication_id": pub_id, "status": "running"}


# ── Integrity checks ─────────────────────────────────────────────────────────


@router.post("/publications/{pub_id}/integrity")
def run_integrity(pub_id: str, current_user: User = Depends(get_current_user)):
    """Stage 5: numbers, citations, ethics, funding, disclosure, compliance."""
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    checks: list[dict] = []

    # Collect verified metric values
    metric_values: set[str] = set()
    metric_count = 0
    with get_db(db) as conn:
        exp_rows = conn.execute(
            """SELECT e.id FROM experiments e
               LEFT JOIN publication_experiments pe
                 ON pe.experiment_id = e.id AND pe.publication_id = ?
               WHERE pe.experiment_id IS NOT NULL
                  OR (pe.experiment_id IS NULL AND e.project_id = ?)
                  OR (e.project_id = ? AND ? IS NOT NULL)""",
            (pub_id, pub.project_id or "", pub.project_id or "", pub.project_id),
        ).fetchall()
        exp_ids = [r["id"] for r in exp_rows]
        if exp_ids:
            q = f"SELECT value FROM experiment_metrics WHERE experiment_id IN ({','.join('?' * len(exp_ids))})"
            for m in conn.execute(q, exp_ids):
                metric_count += 1
                metric_values.add(str(m["value"]).strip())

        # Results text numbers vs metrics
        rows = conn.execute(
            """SELECT content FROM publication_versions
               WHERE publication_id = ?
                 AND (section = 'results' OR section = 'full-draft' OR section IS NULL)
               ORDER BY version DESC LIMIT 5""",
            (pub_id,),
        ).fetchall()
        results_blob = "\n".join(r["content"] or "" for r in rows)

        ai_versions = conn.execute(
            "SELECT COUNT(*) FROM publication_versions WHERE publication_id = ? AND generated_by LIKE 'ai%'",
            (pub_id,),
        ).fetchone()[0]
        human_versions = conn.execute(
            "SELECT COUNT(*) FROM publication_versions WHERE publication_id = ? AND (generated_by IS NULL OR generated_by NOT LIKE 'ai%')",
            (pub_id,),
        ).fetchone()[0]

        irb_ok = conn.execute(
            """SELECT COUNT(*) FROM irb_approvals
               WHERE project_id = ? AND status IN ('approved', 'active')""",
            (pub.project_id or "",),
        ).fetchone()[0]
        grant_ok = conn.execute(
            "SELECT COUNT(*) FROM grants WHERE project_id = ?",
            (pub.project_id or "",),
        ).fetchone()[0]

    # Number check: decimals appearing in results should be in metrics (when metrics exist)
    found_numbers = set(re.findall(r"\b\d+\.\d+\b", results_blob))
    unverified = sorted(found_numbers - metric_values) if metric_count else []
    if metric_count == 0:
        checks.append(
            {
                "id": "numbers",
                "label": "Results numbers verified against metrics",
                "passed": False,
                "detail": "No metrics recorded — Results must not invent numbers.",
            }
        )
    else:
        checks.append(
            {
                "id": "numbers",
                "label": "Results numbers verified against metrics",
                "passed": len(unverified) == 0,
                "detail": (
                    f"{len(found_numbers)} numeric literals; {len(unverified)} not in metrics: {unverified[:8]}"
                    if unverified
                    else f"All {len(found_numbers)} numeric literals match stored metrics."
                ),
            }
        )

    # Ethics
    checks.append(
        {
            "id": "ethics",
            "label": "Approved IRB (if human/PHI research)",
            "passed": irb_ok > 0 or not pub.project_id,
            "detail": f"{irb_ok} approved IRB record(s) on this project",
        }
    )
    # Funding
    checks.append(
        {
            "id": "funding",
            "label": "Funding declaration available",
            "passed": grant_ok > 0,
            "detail": f"{grant_ok} grant(s) on this project",
        }
    )
    # Human revision
    checks.append(
        {
            "id": "human_review",
            "label": "Human revision after AI draft",
            "passed": human_versions >= 1,
            "detail": f"{human_versions} human / {ai_versions} AI versions",
        }
    )
    # AI provenance
    checks.append(
        {
            "id": "provenance",
            "label": "AI provenance recorded",
            "passed": ai_versions >= 1,
            "detail": f"{ai_versions} AI versions with provenance",
        }
    )
    # Compliance fields on publication if present
    for field, label in (
        ("reporting_guideline", "Reporting guideline"),
        ("data_availability", "Data availability"),
        ("code_availability", "Code availability"),
        ("conflict_of_interest", "COI statement"),
        ("funding_statement", "Funding statement"),
    ):
        if hasattr(pub, field):
            val = (getattr(pub, field) or "").strip()
            checks.append(
                {
                    "id": field,
                    "label": label,
                    "passed": bool(val),
                    "detail": val[:80] if val else "empty",
                }
            )

    # ethics only hard-fail when project exists and research needs it — treat as soft if no project
    hard = [c for c in checks if c["id"] in ("numbers", "human_review") and not c["passed"]]
    passed = len(hard) == 0

    run = paper_context.save_integrity_run(db, pub_id, checks, passed)
    return {
        "publication_id": pub_id,
        "passed": passed,
        "checks": checks,
        "run_id": run["id"],
        "blocking": [c["id"] for c in hard],
    }


# ── Pipeline status ──────────────────────────────────────────────────────────


@router.get("/publications/{pub_id}/stages")
def pipeline_status(pub_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    claims = paper_context.list_claim_map(db, pub_id)
    versions = list_versions(db, pub_id)
    sections_done = {v.section for v in versions if v.section and v.content}
    snapshots = paper_context.list_context_snapshots(db, pub_id)

    with get_db(db) as conn:
        last_integrity = conn.execute(
            """SELECT passed, checks_json, created_at FROM paper_integrity_runs
               WHERE publication_id = ? ORDER BY created_at DESC LIMIT 1""",
            (pub_id,),
        ).fetchone()

    stages = {
        "setup": bool(pub.title),
        "evidence": len(snapshots) > 0 or bool(claims),
        "outline": len(claims) > 0,
        "sections": bool(sections_done & {"abstract", "introduction", "methods", "results"}),
        "coherence": "coherence" in sections_done,
        "integrity": bool(last_integrity and last_integrity["passed"]),
        "submit": (pub.status or "draft") in ("submitted", "reviewing", "accepted", "published"),
    }
    return {
        "publication_id": pub_id,
        "status": pub.status,
        "stages": stages,
        "claim_count": len(claims),
        "sections_done": sorted(sections_done),
        "snapshot_count": len(snapshots),
        "integrity": (
            {
                "passed": bool(last_integrity["passed"]),
                "created_at": last_integrity["created_at"],
                "checks": json.loads(last_integrity["checks_json"]),
            }
            if last_integrity
            else None
        ),
    }


# ── Reviewer points ──────────────────────────────────────────────────────────


class ReviewPointRequest(BaseModel):
    comment: str = Field(min_length=1)
    action: str | None = None
    section: str | None = None
    status: str = "open"
    round: int = 1


@router.get("/publications/{pub_id}/review-points")
def list_review_points(pub_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM paper_review_points WHERE publication_id = ? ORDER BY round, created_at",
            (pub_id,),
        ).fetchall()
    return {"points": [dict(r) for r in rows]}


@router.post("/publications/{pub_id}/review-points", status_code=201)
def add_review_point(
    pub_id: str,
    body: ReviewPointRequest,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    if not get_publication(db, pub_id):
        raise HTTPException(status_code=404, detail="Publication not found")
    import uuid
    from datetime import UTC, datetime

    pid = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO paper_review_points
               (id, publication_id, round, comment, action, section, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, pub_id, body.round, body.comment, body.action, body.section, body.status, now),
        )
        row = conn.execute("SELECT * FROM paper_review_points WHERE id = ?", (pid,)).fetchone()
    return dict(row)


@router.put("/publications/{pub_id}/review-points/{point_id}")
def update_review_point(
    pub_id: str,
    point_id: str,
    body: ReviewPointRequest,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    with get_db(db) as conn:
        conn.execute(
            """UPDATE paper_review_points
               SET comment=?, action=?, section=?, status=? WHERE id=? AND publication_id=?""",
            (body.comment, body.action, body.section, body.status, point_id, pub_id),
        )
        row = conn.execute(
            "SELECT * FROM paper_review_points WHERE id = ?", (point_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Review point not found")
    return dict(row)


@router.post("/publications/{pub_id}/submit-pack")
def submit_pack(pub_id: str, current_user: User = Depends(get_current_user)):
    """Stage 7: assemble the submission pack summary (manuscript + provenance + evidence)."""
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    versions = list_versions(db, pub_id)
    claims = paper_context.list_claim_map(db, pub_id)
    snapshots = paper_context.list_context_snapshots(db, pub_id)
    with get_db(db) as conn:
        integrity = conn.execute(
            """SELECT passed, checks_json FROM paper_integrity_runs
               WHERE publication_id = ? ORDER BY created_at DESC LIMIT 1""",
            (pub_id,),
        ).fetchone()
        points = conn.execute(
            "SELECT * FROM paper_review_points WHERE publication_id = ?",
            (pub_id,),
        ).fetchall()

    latest = versions[0] if versions else None
    return {
        "publication_id": pub_id,
        "title": pub.title,
        "status": pub.status,
        "manuscript": {
            "version_id": latest.id if latest else None,
            "length": len(latest.content or "") if latest else 0,
            "section": latest.section if latest else None,
        },
        "claim_map_size": len(claims),
        "evidence_snapshot_id": snapshots[0]["id"] if snapshots else None,
        "ai_disclosure": {
            "ai_versions": sum(1 for v in versions if (v.generated_by or "").startswith("ai")),
            "human_versions": sum(1 for v in versions if not (v.generated_by or "").startswith("ai")),
        },
        "integrity_passed": bool(integrity and integrity["passed"]),
        "open_review_points": sum(1 for p in points if p["status"] == "open"),
    }
