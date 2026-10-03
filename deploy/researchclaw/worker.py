"""AutoResearchClaw worker: runs `researchclaw run` jobs for the PM.

Internal service (Docker network only, bearer token). It never patches ARC; it
only reads and writes ARC's own files in each run directory:

  <RUNS>/<job>/config.arc.yaml        config rendered from env + request
  <RUNS>/<job>/out/heartbeat.json     current stage (written by ARC)
  <RUNS>/<job>/out/hitl/waiting.json  a gate is waiting for a human (ARC)
  <RUNS>/<job>/out/hitl/response.json the human's answer (written here)
  <RUNS>/<job>/out/evolution/lessons.jsonl  lessons: seeded here, extended by ARC
  <RUNS>/<job>/exit_code              written by the shell wrapper on exit
"""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
from pathlib import Path
from typing import Literal

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

RUNS = Path(os.environ.get("ARC_RUNS_DIR", "/runs"))
DATASETS = Path(os.environ.get("ARC_DATASETS_DIR", "/datasets"))
EXPERIMENT_PYTHON = os.environ.get("ARC_EXPERIMENT_PYTHON", "/opt/expvenv/bin/python")
_JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# A gate may wait for a PI for days; ARC aborts (never auto-approves) on timeout.
HUMAN_TIMEOUT_SEC = int(os.environ.get("ARC_HUMAN_TIMEOUT_SEC", str(7 * 86400)))

app = FastAPI(title="AutoResearchClaw worker")


def _auth(authorization: str = Header("")) -> None:
    token = os.environ.get("ARC_WORKER_TOKEN", "")
    if not token or authorization != f"Bearer {token}":
        raise HTTPException(401, "bad token")


class JobRequest(BaseModel):
    job_id: str
    topic: str = Field(min_length=10, max_length=4000)
    mode: Literal["co-pilot", "gate-only", "full-auto", "step-by-step"] = "co-pilot"
    to_stage: str | None = None
    dataset: str | None = None  # path under ARC_DATASETS_DIR, mounted read-only
    lessons: list[dict] = []  # lab lessons to seed, already ranked by the PM


class HumanResponse(BaseModel):
    action: Literal["approve", "reject", "edit", "skip", "rollback", "abort"]
    message: str = ""
    guidance: str = ""
    rollback_to_stage: int | None = None


def _job_dir(job_id: str) -> Path:
    if not _JOB_ID.match(job_id):
        raise HTTPException(400, "bad job id")
    return RUNS / job_id


def _existing(job_id: str) -> Path:
    d = _job_dir(job_id)
    if not (d / "job.json").exists():
        raise HTTPException(404, "no such job")
    return d


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def render_config(req: JobRequest) -> dict:
    """ARC config: Groq (OpenAI-compatible), CPU sandbox, no OpenCode."""
    return {
        "project": {"name": req.job_id, "mode": req.mode},
        "research": {"topic": req.topic, "domains": ["machine-learning"]},
        "runtime": {"timezone": "Europe/Istanbul", "max_parallel_tasks": 1},
        "notifications": {"channel": "console"},
        "knowledge_base": {"backend": "markdown", "root": "kb"},
        "llm": {
            "provider": "openai-compatible",
            "base_url": os.environ.get("ARC_LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            "wire_api": "chat_completions",
            "api_key_env": os.environ.get("ARC_LLM_API_KEY_ENV", "GROQ_API_KEY"),
            "primary_model": os.environ.get("ARC_LLM_MODEL", "openai/gpt-oss-120b"),
            "fallback_models": [os.environ.get("ARC_LLM_FALLBACK", "qwen/qwen3.6-27b")],
        },
        "literature_search": {
            "sources": ["openalex", "semantic_scholar", "arxiv"],
            "max_results_per_query": 20,
            "s2_api_key_env": "S2_API_KEY",
        },
        "security": {"redact_sensitive_logs": True, "allow_publish_without_approval": False},
        "hitl": {
            "mode": req.mode,
            "timeouts": {
                "default_human_timeout_sec": HUMAN_TIMEOUT_SEC,
                "auto_proceed_on_timeout": False,
            },
        },
        "experiment": {
            "mode": "sandbox",
            "time_budget_sec": int(os.environ.get("ARC_TIME_BUDGET_SEC", "900")),
            "max_iterations": 5,
            "sandbox": {"python_path": EXPERIMENT_PYTHON, "gpu_required": False, "max_memory_mb": 4096},
            "opencode": {"enabled": False},
        },
    }


def _topic_with_dataset(req: JobRequest) -> str:
    if not req.dataset:
        return req.topic
    path = (DATASETS / req.dataset).resolve()
    if DATASETS.resolve() not in path.parents or not path.exists():
        raise HTTPException(400, "dataset not found under the datasets root")
    return (
        f"{req.topic}\n\nData: use only the read-only dataset at {path}. It may contain "
        "patient data: never print rows, identifiers or free text to logs; report "
        "aggregate metrics only."
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/jobs", status_code=201, dependencies=[Depends(_auth)])
def start_job(req: JobRequest) -> dict:
    d = _job_dir(req.job_id)
    if d.exists():
        raise HTTPException(409, "job exists")
    topic = _topic_with_dataset(req)
    (d / "out" / "evolution").mkdir(parents=True)
    cfg = render_config(req.model_copy(update={"topic": topic}))
    (d / "config.arc.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    with (d / "out" / "evolution" / "lessons.jsonl").open("w", encoding="utf-8") as f:
        for lesson in req.lessons:
            f.write(json.dumps(lesson) + "\n")
    cmd = ["researchclaw", "run", "-c", "config.arc.yaml", "-o", "out", "--mode", req.mode, "--skip-preflight"]
    if req.mode == "full-auto":
        cmd.append("--auto-approve")
    if req.to_stage:
        cmd += ["--to-stage", req.to_stage]
    # The shell records the exit code so status survives a worker restart.
    shell = f"{shlex.join(cmd)} > run.log 2>&1; echo $? > exit_code"
    proc = subprocess.Popen(["sh", "-c", shell], cwd=d, start_new_session=True, stdin=subprocess.DEVNULL)
    (d / "job.json").write_text(json.dumps({"pid": proc.pid, "mode": req.mode}), encoding="utf-8")
    return {"job_id": req.job_id, "state": "running"}


def _first_error(out: Path) -> str | None:
    for health in sorted(out.glob("stage-*/stage_health.json")):
        h = _read_json(health) or {}
        if h.get("status") == "failed":
            return f"{h.get('stage_id')}: {h.get('error')}"
    return None


def job_status(d: Path) -> dict:
    out = d / "out"
    beat = _read_json(out / "heartbeat.json") or {}
    waiting = _read_json(out / "hitl" / "waiting.json")
    summary = _read_json(out / "pipeline_summary.json") or {}
    exit_file = d / "exit_code"
    exit_code = int(exit_file.read_text().strip()) if exit_file.exists() else None
    if (d / "cancelled").exists():
        state = "cancelled"
    elif exit_code is not None:
        # ARC exits 0 even when a stage failed; its summary says what happened.
        ok = exit_code == 0 and summary.get("final_status") == "done" and not summary.get("stages_failed")
        state = "done" if ok else "failed"
    elif waiting and not (out / "hitl" / "response.json").exists():
        state = "waiting"
    else:
        state = "running"
    return {
        "state": state,
        "stage": beat.get("last_stage"),
        "stage_name": beat.get("last_stage_name"),
        "arc_run_id": beat.get("run_id"),
        "updated_at": beat.get("timestamp"),
        "waiting": waiting if state == "waiting" else None,
        "exit_code": exit_code,
        "stages_done": summary.get("stages_done"),
        "stages_failed": summary.get("stages_failed"),
        "error": _first_error(out) if state == "failed" else None,
    }


@app.get("/jobs/{job_id}", dependencies=[Depends(_auth)])
def get_job(job_id: str) -> dict:
    return job_status(_existing(job_id))


@app.post("/jobs/{job_id}/response", dependencies=[Depends(_auth)])
def respond(job_id: str, body: HumanResponse) -> dict:
    hitl = _existing(job_id) / "out" / "hitl"
    if not (hitl / "waiting.json").exists():
        raise HTTPException(409, "the run is not waiting for input")
    (hitl / "response.json").write_text(json.dumps(body.model_dump()), encoding="utf-8")
    return {"status": "sent"}


@app.post("/jobs/{job_id}/cancel", dependencies=[Depends(_auth)])
def cancel(job_id: str) -> dict:
    d = _existing(job_id)
    pid = (_read_json(d / "job.json") or {}).get("pid")
    (d / "cancelled").touch()
    if pid:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    return {"state": "cancelled"}


@app.get("/jobs/{job_id}/lessons", dependencies=[Depends(_auth)])
def lessons(job_id: str) -> list[dict]:
    path = _existing(job_id) / "out" / "evolution" / "lessons.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@app.get("/jobs/{job_id}/registry", dependencies=[Depends(_auth)])
def registry(job_id: str) -> dict:
    """Every number the experiments produced (ARC's VerifiedRegistry)."""
    from researchclaw.pipeline.verified_registry import VerifiedRegistry

    reg = VerifiedRegistry.from_run_dir(_existing(job_id) / "out", best_only=True)
    return {
        "primary_metric": reg.primary_metric,
        "primary_metric_std": reg.primary_metric_std,
        "metric_direction": reg.metric_direction,
        "conditions": sorted(reg.condition_names),
        "values": [[v, src] for v, src in reg.values.items() if "rounded" not in src and "×100" not in src and "÷100" not in src],
    }


@app.get("/jobs/{job_id}/file", dependencies=[Depends(_auth)])
def read_file(job_id: str, path: str) -> dict:
    """A text artifact of the run (reports, decisions), confined to the run dir."""
    base = (_existing(job_id) / "out").resolve()
    target = (base / path).resolve()
    if base not in target.parents or not target.is_file():
        raise HTTPException(404, "no such file")
    if target.stat().st_size > 2_000_000:
        raise HTTPException(413, "file too large")
    return {"path": path, "content": target.read_text(encoding="utf-8", errors="replace")}
