"""AutoResearchClaw integration: worker client, gate permissions, result import.

The worker (deploy/researchclaw/worker.py) runs ARC; this module talks to it
and maps its results into PM data. See plan/autoresearchclaw-integration.md.
"""

from __future__ import annotations

import json
import logging
import math
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from . import settings
from .db import get_db
from .metrics_csv import ParsedMetric

logger = logging.getLogger(__name__)

# Stages from RESULT_ANALYSIS on judge results and the paper (paper §4.4,
# "post-experiment HITL"): a lab PI decides those gates, not the student.
FIRST_POST_EXPERIMENT_STAGE = 14
SEVERITY = {"error": 1.0, "warning": 0.6, "info": 0.3}
HALF_LIFE_DAYS = 30.0
MAX_SEEDED_LESSONS = 200
# Operational failures (provider limits, outages) are not research lessons;
# seeding them would steer later runs away from sound designs.
_INFRA_ERROR = re.compile(r"HTTP Error|rate.?limit|All models failed|timed? ?out|Connection", re.IGNORECASE)


class WorkerError(RuntimeError):
    """The worker refused the request or could not be reached.

    ``retryable`` is True when the worker was unreachable: a queued run then
    stays queued instead of failing.
    """

    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


def _call(method: str, path: str, json_body: dict | None = None, timeout: float = 15) -> Any:
    cfg = settings.get_arc_worker_config()
    if not cfg["token"]:
        raise WorkerError("AutoResearchClaw worker is not configured (ARC_WORKER_TOKEN)")
    try:
        resp = httpx.request(
            method,
            f"{cfg['url']}{path}",
            json=json_body,
            headers={"Authorization": f"Bearer {cfg['token']}"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise WorkerError(f"AutoResearchClaw worker unreachable: {exc}", retryable=True) from exc
    if resp.status_code >= 400:
        raise WorkerError(f"worker {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def is_post_experiment_gate(stage: int | None) -> bool:
    return stage is not None and stage >= FIRST_POST_EXPERIMENT_STAGE


def lesson_weight(severity: float, created_at: datetime, now: datetime | None = None) -> float:
    """Paper eq. (1): w = s * exp(-ln2 * age / T_half)."""
    age_days = ((now or datetime.now(UTC)) - created_at).total_seconds() / 86400
    return severity * math.exp(-math.log(2) * max(age_days, 0.0) / HALF_LIFE_DAYS)


def is_research_lesson(lesson: dict) -> bool:
    return not _INFRA_ERROR.search(str(lesson.get("description", "")))


def lab_lessons_to_seed(db: Path, lab_id: str | None) -> list[dict]:
    """The lab's lessons in ARC's own format: pinned first, then by recency weight."""
    if not lab_id:
        return []
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT severity, lesson_json, pinned, created_at FROM research_lessons WHERE lab_id = ?", (lab_id,)
        ).fetchall()
    ranked = sorted(
        rows,
        key=lambda r: (r["pinned"], lesson_weight(r["severity"], datetime.fromisoformat(r["created_at"]))),
        reverse=True,
    )
    return [json.loads(r["lesson_json"]) for r in ranked[:MAX_SEEDED_LESSONS]]


# Templates for the start form. ``profile`` is an ARC domain profile that runs in the
# CPU sandbox; the guidance is appended to the research question.
DOMAINS: dict[str, dict] = {
    "ml": {"label": "Machine learning (tabular data)", "profile": "ml_tabular",
           "guidance": "Compare against simple baselines; report mean ± std over at least 5 seeds."},
    "clinical": {"label": "Clinical / observational study", "profile": "medical_observational",
                 "guidance": "State the estimand, adjust for confounders, report confidence intervals; aggregate results only."},
    "imaging": {"label": "Medical imaging", "profile": None,
                "guidance": "CPU only: use small models or pretrained features; report AUC, sensitivity and specificity with confidence intervals."},
    "statistics": {"label": "Statistics / simulation", "profile": None,
                   "guidance": "Monte Carlo with fixed seeds; report bias, coverage and RMSE."},
}


def topic_for(topic: str, domain: str | None) -> str:
    guidance = DOMAINS.get(domain or "", {}).get("guidance")
    return f"{topic}\n\nMethod guidance: {guidance}" if guidance else topic


def start(run_id: str, topic: str, mode: str, dataset: str | None, lessons: list[dict], domain: str | None = None) -> dict:
    return _call("POST", "/jobs", {
        "job_id": run_id, "topic": topic_for(topic, domain), "mode": mode, "dataset": dataset,
        "lessons": lessons, "profile": DOMAINS.get(domain or "", {}).get("profile"),
    })


def stage_stats(stage_list: list[dict]) -> dict:
    """Self-healing at a glance (paper §3.3): how often the run refined, pivoted or retried."""
    return {
        "stages_done": sum(1 for s in stage_list if s.get("status") in ("done", "approved")),
        "refines": sum(1 for s in stage_list if s.get("decision") == "refine"),
        "pivots": sum(1 for s in stage_list if s.get("decision") == "pivot"),
        "retries": sum(max(0, int(s.get("attempts") or 1) - 1) for s in stage_list),
        "failed_stages": sum(1 for s in stage_list if s.get("status") == "failed"),
    }


def deliverables(run_id: str) -> dict:
    return _call("GET", f"/jobs/{run_id}/deliverables", timeout=60)


def stages(run_id: str) -> dict:
    return _call("GET", f"/jobs/{run_id}/stages")


def status(run_id: str) -> dict:
    return _call("GET", f"/jobs/{run_id}")


def respond(run_id: str, decision: dict) -> dict:
    return _call("POST", f"/jobs/{run_id}/response", decision)


def cancel(run_id: str) -> dict:
    return _call("POST", f"/jobs/{run_id}/cancel")


def read_file(run_id: str, path: str) -> dict:
    return _call("GET", f"/jobs/{run_id}/file?{urlencode({'path': path})}")


def import_results(db: Path, run: dict) -> None:
    """Copy a finished run's verified numbers and lessons into the PM (once)."""
    now = datetime.now(UTC).isoformat()
    try:
        registry = _call("GET", f"/jobs/{run['id']}/registry", timeout=60)
    except WorkerError as exc:
        logger.warning("registry import skipped for %s: %s", run["id"], exc)
        registry = {"values": []}
    lessons = [lesson for lesson in _call("GET", f"/jobs/{run['id']}/lessons") if is_research_lesson(lesson)]

    from .crud.experiment_metrics import create_metrics

    metrics = [
        ParsedMetric(name=f"[ARC {run['id'][:8]}] {source}"[:200], value=float(value))
        for value, source in registry.get("values", [])
    ]
    if metrics:
        create_metrics(db, run["experiment_id"], metrics, recorded_by=None)
    from .crud.research_runs import set_result_summary, set_stage_stats

    set_result_summary(db, run["id"], registry)
    try:
        set_stage_stats(db, run["id"], stage_stats(stages(run["id"])["stages"]))
    except WorkerError as exc:
        logger.warning("stage stats skipped for %s: %s", run["id"], exc)
    with get_db(db) as conn:
        for lesson in lessons:
            conn.execute(
                """INSERT OR IGNORE INTO research_lessons
                   (id, lab_id, run_id, category, severity, lesson_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    uuid.uuid4().hex, run["lab_id"], run["id"],
                    str(lesson.get("category", "general")),
                    SEVERITY.get(str(lesson.get("severity")), 0.3),
                    json.dumps(lesson, sort_keys=True),
                    str(lesson.get("timestamp") or now),
                ),
            )
        conn.execute("UPDATE research_runs SET imported_at = ? WHERE id = ?", (now, run["id"]))
