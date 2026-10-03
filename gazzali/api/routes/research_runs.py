"""AutoResearchClaw runs: start from an experiment, answer gates, read lab lessons.

Runs live in the ARC worker; the PM mirrors them (``research_sync``). A new run is
queued and dispatched while capacity allows. Gate rule (paper §4.4): before the
experiment the project's owner/editor decides; from result analysis on, a leader
of the project's lab (or a platform admin) does.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ... import research_claw as arc
from ... import research_sync as sync
from ... import settings
from ..._ai import run_llm_direct_async
from ...crud import research_runs as runs_db
from ...crud.ai_usage import UsageContext
from ...crud.experiments import get_experiment
from ...crud.irb import get_irb
from ...crud.labs import get_member_role as get_lab_member_role
from ...crud.projects import get_member_role, get_project
from ...db import get_db, get_db_path
from ...models import User
from ...supervision_scope import led_lab_ids
from ..audit_helper import log_action
from ..deps import get_current_user, require_project_role

router = APIRouter()

Mode = Literal["co-pilot", "gate-only", "full-auto", "step-by-step"]
QUALITY_GATE_STAGE = 20
# Datasets a run may use: approved by the PI and the platform admin.
_USABLE_DATASET = ("approved", "delivering", "sealed")


class StartRun(BaseModel):
    topic: str | None = Field(default=None, max_length=4000)
    mode: Mode = "co-pilot"
    domain: Literal["ml", "clinical", "imaging", "statistics"] | None = None
    dataset_id: str | None = None
    irb_id: str | None = None


class GateDecision(BaseModel):
    action: Literal["approve", "reject", "edit", "skip", "rollback", "abort"]
    message: str = Field(default="", max_length=4000)
    guidance: str = Field(default="", max_length=4000)
    rollback_to_stage: int | None = Field(default=None, ge=1, le=23)
    quality: int | None = Field(default=None, ge=1, le=10)  # PI's score at the final quality gate


class TopicCheck(BaseModel):
    topic: str = Field(min_length=10, max_length=4000)
    domain: str | None = None


class Pin(BaseModel):
    pinned: bool


def can_decide(db, user: User, run: dict) -> bool:
    if user.is_admin:
        return True
    if arc.is_post_experiment_gate(run.get("stage")):
        if run["lab_id"]:
            return run["lab_id"] in led_lab_ids(db, user.id)
        return get_member_role(db, run["project_id"], user.id) == "owner"
    return get_member_role(db, run["project_id"], user.id) in ("owner", "editor")


def can_view(db, user: User, run: dict) -> bool:
    return (
        user.is_admin
        or get_member_role(db, run["project_id"], user.id) is not None
        or (run["lab_id"] is not None and run["lab_id"] in led_lab_ids(db, user.id))
    )


def _with_queue(db, runs: list[dict]) -> list[dict]:
    positions = runs_db.queue_positions(db)
    return [{**r, "queue_position": positions.get(r["id"])} for r in runs]


def _irb_active(db, project_id: str, irb_id: str | None) -> bool:
    irb = get_irb(db, irb_id) if irb_id else None
    today = datetime.now(UTC).date().isoformat()
    return bool(
        irb and irb.project_id == project_id and irb.status == "approved"
        and not (irb.expiry_date and irb.expiry_date < today)
    )


def _usable_datasets(db, project_id: str, lab_id: str | None) -> list[dict]:
    """The lab's approved datasets, each with this project's active IRBs that cover it."""
    if not lab_id:
        return []
    with get_db(db) as conn:
        rows = conn.execute(
            f"""SELECT d.id, d.name, d.modality, d.status, di.irb_id
                  FROM datasets d JOIN dataset_irbs di ON di.dataset_id = d.id
                 WHERE d.lab_id = ? AND d.status IN ({','.join('?' * len(_USABLE_DATASET))})
                 ORDER BY d.name""",
            (lab_id, *_USABLE_DATASET),
        ).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        if _irb_active(db, project_id, r["irb_id"]):
            entry = out.setdefault(r["id"], {"id": r["id"], "name": r["name"], "modality": r["modality"], "irb_ids": []})
            entry["irb_ids"].append(r["irb_id"])
    return list(out.values())


@router.get("/research-runs/domains")
def domains(current_user: User = Depends(get_current_user)):
    return [{"id": k, "label": v["label"], "guidance": v["guidance"]} for k, v in arc.DOMAINS.items()]


@router.get("/projects/{project_id}/research-datasets")
def research_datasets(project_id: str, current_user: User = Depends(require_project_role("owner", "editor"))):
    db = get_db_path()
    project = get_project(db, project_id)
    return _usable_datasets(db, project_id, project.lab_id if project else None)


@router.post("/research-runs/topic-check")
async def topic_check(body: TopicCheck, current_user: User = Depends(get_current_user)):
    """Score a research question the way ARC does in stage 2, before anything starts."""
    system = (
        "You review research questions before an automated research pipeline runs them on CPU within "
        "a limited time budget. Score 0-10: novelty, specificity, feasibility, overall. Give one concrete "
        "suggestion that would raise the overall score (empty if none). Respond with JSON only: "
        '{"novelty": n, "specificity": n, "feasibility": n, "overall": n, "suggestion": "..."}'
    )
    text = await run_llm_direct_async(
        system, arc.topic_for(body.topic, body.domain), temperature=0.1,
        context=UsageContext(task="topic-check", user_id=current_user.id),
    )
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        data = json.loads(match.group(0)) if match else {}
        return {k: data[k] for k in ("novelty", "specificity", "feasibility", "overall")} | {
            "suggestion": str(data.get("suggestion") or "")}
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise HTTPException(502, "the model did not return a score; try again") from exc


@router.get("/research-runs/usage")
def usage(current_user: User = Depends(get_current_user)):
    return sync.usage(get_db_path())


@router.post("/projects/{project_id}/experiments/{experiment_id}/research-runs", status_code=201)
def start_run(
    project_id: str,
    experiment_id: str,
    body: StartRun,
    request: Request,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    db = get_db_path()
    exp = get_experiment(db, experiment_id)
    if exp is None or exp.project_id != project_id:
        raise HTTPException(404, "Experiment not found")
    project = get_project(db, project_id)
    lab_id = project.lab_id if project else None
    if body.dataset_id:
        usable = {d["id"]: d for d in _usable_datasets(db, project_id, lab_id)}
        if body.dataset_id not in usable or body.irb_id not in usable[body.dataset_id]["irb_ids"]:
            raise HTTPException(400, "choose an approved dataset of this lab and an active IRB of this project that covers it")
    topic = (body.topic or exp.hypothesis or exp.name or "").strip()
    if len(topic) < 10:
        raise HTTPException(400, "describe the research question (at least 10 characters)")
    if not settings.get_arc_worker_config()["token"]:
        raise HTTPException(503, "AutoResearchClaw is not set up on this server yet")
    run = runs_db.create_run(
        db, experiment_id=experiment_id, project_id=project_id, lab_id=lab_id,
        started_by=current_user.id, topic=topic, mode=body.mode, domain=body.domain,
        dataset=body.dataset_id, irb_id=body.irb_id if body.dataset_id else None,
    )
    sync.dispatch(db)
    log_action(request, current_user, "start", "research_run", run["id"], f"{body.mode} on experiment {experiment_id}")
    return _with_queue(db, [runs_db.get_run(db, run["id"]) or run])[0]


@router.get("/projects/{project_id}/experiments/{experiment_id}/research-runs")
def list_runs(
    project_id: str,
    experiment_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    db = get_db_path()
    runs = [sync.refresh(db, r) for r in runs_db.list_runs(db, experiment_id) if r["project_id"] == project_id]
    return _with_queue(db, runs)


@router.get("/research-runs/gates")
def pending_gates(current_user: User = Depends(get_current_user)):
    """Runs waiting for a decision this user may take."""
    db = get_db_path()
    active = [sync.refresh(db, r) for r in runs_db.list_active_runs(db) if can_view(db, current_user, r)]
    return [r for r in active if r["status"] == "waiting" and can_decide(db, current_user, r)]


def _visible_run(db, run_id: str, user: User) -> dict:
    run = runs_db.get_run(db, run_id)
    if run is None or not can_view(db, user, run):
        raise HTTPException(404, "Run not found")
    return sync.refresh(db, run)


@router.get("/research-runs/{run_id}/stages")
def run_stages(run_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    run = _visible_run(db, run_id, current_user)
    if run["status"] == "queued":
        return {"stages": [], "topic_evaluation": None}
    try:
        return arc.stages(run_id)
    except arc.WorkerError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/research-runs/{run_id}/respond")
def respond(run_id: str, body: GateDecision, request: Request, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    run = _visible_run(db, run_id, current_user)
    if run["status"] != "waiting":
        raise HTTPException(409, "the run is not waiting for a decision")
    if not can_decide(db, current_user, run):
        who = "a PI of this lab" if arc.is_post_experiment_gate(run["stage"]) else "the project owner or an editor"
        raise HTTPException(403, f"this gate is decided by {who}")
    try:
        arc.respond(run_id, body.model_dump(exclude={"quality"}))
    except arc.WorkerError as exc:
        raise HTTPException(503, str(exc)) from exc
    if body.quality is not None and run["stage"] == QUALITY_GATE_STAGE:
        runs_db.set_pi_quality(db, run_id, body.quality)
    runs_db.set_status(db, run_id, "running")
    log_action(request, current_user, body.action, "research_run", run_id,
               json.dumps({"stage": run["stage"], "stage_name": run["stage_name"], "message": body.message[:200]}))
    return runs_db.get_run(db, run_id)


@router.get("/research-runs/{run_id}/file")
def read_file(run_id: str, path: str, current_user: User = Depends(get_current_user)):
    """A text artifact of the run (hypotheses, design, draft) for whoever reviews a gate."""
    db = get_db_path()
    run = runs_db.get_run(db, run_id)
    if run is None or not can_view(db, current_user, run):
        raise HTTPException(404, "Run not found")
    try:
        return arc.read_file(run_id, path)
    except arc.WorkerError as exc:
        raise HTTPException(404 if "404" in str(exc) else 503, str(exc)) from exc


@router.post("/research-runs/{run_id}/cancel")
def cancel(run_id: str, request: Request, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    run = _visible_run(db, run_id, current_user)
    allowed = current_user.is_admin or get_member_role(db, run["project_id"], current_user.id) in ("owner", "editor") \
        or (run["lab_id"] and run["lab_id"] in led_lab_ids(db, current_user.id))
    if not allowed:
        raise HTTPException(403, "not permitted")
    if run["status"] not in runs_db.OPEN:
        raise HTTPException(409, "the run has already ended")
    if run["status"] != "queued":
        try:
            arc.cancel(run_id)
        except arc.WorkerError as exc:
            raise HTTPException(503, str(exc)) from exc
    runs_db.set_status(db, run_id, "cancelled")
    sync.dispatch(db)
    log_action(request, current_user, "cancel", "research_run", run_id)
    return runs_db.get_run(db, run_id)


def _lab_reader(db, lab_id: str, user: User) -> None:
    # A PI can be recorded only as labs.pi_id, without a lab_members row.
    member = get_lab_member_role(db, lab_id, user.id) is not None
    if not (user.is_admin or member or lab_id in led_lab_ids(db, user.id)):
        raise HTTPException(403, "lab membership required")


def _lab_leader(db, lab_id: str, user: User) -> None:
    if not (user.is_admin or lab_id in led_lab_ids(db, user.id)):
        raise HTTPException(403, "only a PI of this lab can change its research memory")


@router.get("/labs/{lab_id}/research-lessons")
def list_lessons(lab_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    _lab_reader(db, lab_id, current_user)
    lessons = runs_db.list_lessons(db, lab_id)
    now = datetime.now(UTC)
    for entry in lessons:
        entry["weight"] = round(arc.lesson_weight(entry["severity"], datetime.fromisoformat(entry["created_at"]), now), 3)
    return lessons


@router.patch("/labs/{lab_id}/research-lessons/{lesson_id}")
def pin_lesson(lab_id: str, lesson_id: str, body: Pin, request: Request, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    _lab_leader(db, lab_id, current_user)
    if not runs_db.set_lesson_pinned(db, lab_id, lesson_id, body.pinned):
        raise HTTPException(404, "Lesson not found")
    log_action(request, current_user, "pin" if body.pinned else "unpin", "research_lesson", lesson_id)
    return {"id": lesson_id, "pinned": body.pinned}


@router.delete("/labs/{lab_id}/research-lessons/{lesson_id}", status_code=204)
def delete_lesson(lab_id: str, lesson_id: str, request: Request, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    _lab_leader(db, lab_id, current_user)
    if not runs_db.delete_lesson(db, lab_id, lesson_id):
        raise HTTPException(404, "Lesson not found")
    log_action(request, current_user, "delete", "research_lesson", lesson_id)
