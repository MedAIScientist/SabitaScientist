"""AutoResearchClaw runs: start from an experiment, answer gates, read lab lessons.

Runs live in the ARC worker; the PM mirrors them and refreshes a run whenever it
is read (no background loop). Gate rule (paper §4.4): before the experiment the
project's owner/editor decides; from result analysis on, a leader of the
project's lab (or a platform admin) does.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ... import research_claw as arc
from ...crud import research_runs as runs_db
from ...crud.experiments import get_experiment
from ...crud.irb import get_irb
from ...crud.labs import get_member_role as get_lab_member_role
from ...crud.projects import get_member_role, get_project
from ...db import get_db_path
from ...models import User
from ...supervision_scope import led_lab_ids
from ..audit_helper import log_action
from ..deps import get_current_user, require_project_role

router = APIRouter()


class StartRun(BaseModel):
    topic: str | None = Field(default=None, max_length=4000)
    mode: Literal["co-pilot", "gate-only", "full-auto", "step-by-step"] = "co-pilot"
    dataset: str | None = Field(default=None, max_length=500)
    irb_id: str | None = None


class GateDecision(BaseModel):
    action: Literal["approve", "reject", "edit", "skip", "rollback", "abort"]
    message: str = Field(default="", max_length=4000)
    guidance: str = Field(default="", max_length=4000)
    rollback_to_stage: int | None = Field(default=None, ge=1, le=23)


def refresh(db, run: dict) -> dict:
    """Pull the worker's view of an active run; import results once it ends."""
    if run["status"] in runs_db.ACTIVE:
        try:
            runs_db.update_from_worker(db, run["id"], arc.status(run["id"]))
        except arc.WorkerError:
            return run  # worker down: show the last known state
        run = runs_db.get_run(db, run["id"]) or run
    if run["status"] in ("done", "failed") and not run["imported_at"]:
        try:
            arc.import_results(db, run)
        except arc.WorkerError:
            pass
        run = runs_db.get_run(db, run["id"]) or run
    return run


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


def _irb_ok(db, project_id: str, irb_id: str | None) -> None:
    irb = get_irb(db, irb_id) if irb_id else None
    if irb is None or irb.project_id != project_id:
        raise HTTPException(400, "a dataset needs an IRB approval of this project")
    today = datetime.now(UTC).date().isoformat()
    if irb.status != "approved" or (irb.expiry_date and irb.expiry_date < today):
        raise HTTPException(400, "the IRB approval is not active")


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
    if body.dataset:
        _irb_ok(db, project_id, body.irb_id)
    topic = (body.topic or exp.hypothesis or exp.name or "").strip()
    if len(topic) < 10:
        raise HTTPException(400, "describe the research question (at least 10 characters)")
    project = get_project(db, project_id)
    lab_id = project.lab_id if project else None
    run = runs_db.create_run(
        db, experiment_id=experiment_id, project_id=project_id, lab_id=lab_id,
        started_by=current_user.id, topic=topic, mode=body.mode,
        dataset=body.dataset, irb_id=body.irb_id if body.dataset else None,
    )
    try:
        arc.start(run["id"], topic, body.mode, body.dataset, arc.lab_lessons_to_seed(db, lab_id))
    except arc.WorkerError as exc:
        runs_db.set_status(db, run["id"], "failed", str(exc))
        raise HTTPException(503, str(exc)) from exc
    log_action(request, current_user, "start", "research_run", run["id"], f"{body.mode} on experiment {experiment_id}")
    return runs_db.get_run(db, run["id"])


@router.get("/projects/{project_id}/experiments/{experiment_id}/research-runs")
def list_runs(
    project_id: str,
    experiment_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    db = get_db_path()
    return [refresh(db, r) for r in runs_db.list_runs(db, experiment_id) if r["project_id"] == project_id]


@router.get("/research-runs/gates")
def pending_gates(current_user: User = Depends(get_current_user)):
    """Runs waiting for a decision this user may take."""
    db = get_db_path()
    active = [refresh(db, r) for r in runs_db.list_active_runs(db) if can_view(db, current_user, r)]
    return [r for r in active if r["status"] == "waiting" and can_decide(db, current_user, r)]


def _visible_run(db, run_id: str, user: User) -> dict:
    run = runs_db.get_run(db, run_id)
    if run is None or not can_view(db, user, run):
        raise HTTPException(404, "Run not found")
    return refresh(db, run)


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
        arc.respond(run_id, body.model_dump())
    except arc.WorkerError as exc:
        raise HTTPException(503, str(exc)) from exc
    runs_db.set_status(db, run_id, "running")
    log_action(request, current_user, body.action, "research_run", run_id, f"stage {run['stage']} {run['stage_name']}: {body.message[:200]}")
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
    if run["status"] not in runs_db.ACTIVE:
        raise HTTPException(409, "the run has already ended")
    try:
        arc.cancel(run_id)
    except arc.WorkerError as exc:
        raise HTTPException(503, str(exc)) from exc
    runs_db.set_status(db, run_id, "cancelled")
    log_action(request, current_user, "cancel", "research_run", run_id)
    return runs_db.get_run(db, run_id)


@router.get("/labs/{lab_id}/research-lessons")
def list_lessons(lab_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    # A PI can be recorded only as labs.pi_id, without a lab_members row.
    member = get_lab_member_role(db, lab_id, current_user.id) is not None
    if not (current_user.is_admin or member or lab_id in led_lab_ids(db, current_user.id)):
        raise HTTPException(403, "lab membership required")
    return runs_db.list_lessons(db, lab_id)


@router.delete("/labs/{lab_id}/research-lessons/{lesson_id}", status_code=204)
def delete_lesson(lab_id: str, lesson_id: str, request: Request, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    if not (current_user.is_admin or lab_id in led_lab_ids(db, current_user.id)):
        raise HTTPException(403, "only a PI of this lab can remove lessons")
    if not runs_db.delete_lesson(db, lab_id, lesson_id):
        raise HTTPException(404, "Lesson not found")
    log_action(request, current_user, "delete", "research_lesson", lesson_id)
