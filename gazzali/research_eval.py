"""How AutoResearchClaw runs go in this lab (plan §6): our numbers, not the paper's.

Per run: completion, self-healing (refines, pivots, retries), human interventions
from the audit log, unverified numbers in the resulting paper and the PI's score.
Per gate stage: how often people approve vs redirect (a SmartPause-style hint;
nothing is skipped automatically).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .crud import research_runs as runs_db
from .db import get_db

DECISIONS = ("approve", "reject", "edit", "skip", "rollback", "abort")
MIN_DECISIONS_FOR_ADVICE = 5


def _decisions(db: Path, run_ids: list[str]) -> list[dict]:
    if not run_ids:
        return []
    with get_db(db) as conn:
        rows = conn.execute(
            f"""SELECT entity_id, action, details FROM audit_log
                 WHERE entity_type = 'research_run' AND action IN ({','.join('?' * len(DECISIONS))})
                   AND entity_id IN ({','.join('?' * len(run_ids))})""",
            (*DECISIONS, *run_ids),
        ).fetchall()
    out = []
    for r in rows:
        try:
            details = json.loads(r["details"] or "{}")
        except json.JSONDecodeError:
            continue  # not one of our gate decisions
        if isinstance(details, dict) and "stage" in details:
            out.append({"run_id": r["entity_id"], "action": r["action"], "stage": details["stage"],
                        "stage_name": details.get("stage_name")})
    return out


def _unverified_in_paper(db: Path, publication_id: str | None) -> int | None:
    if not publication_id:
        return None
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT verification_json FROM publication_versions WHERE publication_id = ? ORDER BY version DESC LIMIT 1",
            (publication_id,),
        ).fetchone()
    if not row or not row["verification_json"]:
        return None
    return json.loads(row["verification_json"]).get("unverified_in_results")


def _advice(approved: int, total: int) -> str:
    if total < MIN_DECISIONS_FOR_ADVICE:
        return f"Too few decisions yet ({total}) to judge."
    rate = approved / total
    if rate >= 0.9:
        return "Almost always approved: for routine runs, Gate-only mode would save this step."
    if rate <= 0.6:
        return "Often redirected here: keep reviewing this gate."
    return "Mixed: keep reviewing."


def evaluate(db: Path, lab_ids: list[str] | None) -> dict:
    """``lab_ids`` None = all runs (platform admin)."""
    with get_db(db) as conn:
        if lab_ids is None:
            rows = conn.execute("SELECT id FROM research_runs ORDER BY created_at DESC").fetchall()
        elif lab_ids:
            rows = conn.execute(
                f"SELECT id FROM research_runs WHERE lab_id IN ({','.join('?' * len(lab_ids))}) ORDER BY created_at DESC",
                lab_ids,
            ).fetchall()
        else:
            rows = []
    runs = [runs_db.get_run(db, r["id"]) for r in rows]
    runs = [r for r in runs if r]
    decisions = _decisions(db, [r["id"] for r in runs])
    per_run = defaultdict(int)
    for d in decisions:
        per_run[d["run_id"]] += 1
    out_runs = []
    for r in runs:
        stats = r.get("stage_stats") or {}
        out_runs.append({
            "id": r["id"], "topic": r["topic"], "status": r["status"], "mode": r["mode"],
            "created_at": r["created_at"], "stage": r["stage"], "interventions": per_run[r["id"]],
            "refines": stats.get("refines"), "pivots": stats.get("pivots"), "retries": stats.get("retries"),
            "unverified_in_paper": _unverified_in_paper(db, r.get("publication_id")),
            "pi_quality": r.get("pi_quality"), "primary_metric": r.get("primary_metric"),
        })
    ended = [r for r in runs if r["status"] in ("done", "failed", "cancelled")]
    scored = [r["pi_quality"] for r in runs if r.get("pi_quality")]
    by_stage: dict[int, dict] = {}
    for d in decisions:
        s = by_stage.setdefault(d["stage"], {"stage": d["stage"], "stage_name": d["stage_name"], "approved": 0, "redirected": 0})
        if d["action"] == "approve":
            s["approved"] += 1
        else:
            s["redirected"] += 1
    gates = []
    for s in sorted(by_stage.values(), key=lambda x: x["stage"]):
        total = s["approved"] + s["redirected"]
        gates.append({**s, "total": total, "approve_rate": round(s["approved"] / total, 2), "advice": _advice(s["approved"], total)})
    return {
        "summary": {
            "runs": len(runs),
            "finished": sum(1 for r in runs if r["status"] == "done"),
            "completion_rate": round(sum(1 for r in ended if r["status"] == "done") / len(ended), 2) if ended else None,
            "mean_interventions": round(sum(per_run.values()) / len(runs), 1) if runs else None,
            "mean_pi_quality": round(sum(scored) / len(scored), 1) if scored else None,
        },
        "runs": out_runs,
        "gates": gates,
    }
