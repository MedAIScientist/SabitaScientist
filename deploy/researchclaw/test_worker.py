"""Worker checks: run inside the worker image (`python -m pytest test_worker.py`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import worker


def _write(path: Path, data: dict | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data))


def _job(tmp_path: Path) -> Path:
    d = tmp_path / "j1"
    _write(d / "job.json", {"pid": 0})
    _write(d / "out" / "heartbeat.json", {"last_stage": 5, "last_stage_name": "LITERATURE_SCREEN"})
    return d


def test_exit_zero_with_a_failed_stage_is_failed(tmp_path: Path) -> None:
    d = _job(tmp_path)
    _write(d / "exit_code", "0\n")
    _write(d / "out" / "pipeline_summary.json", {"final_status": "failed", "stages_failed": 1, "stages_done": 4})
    _write(d / "out" / "stage-05" / "stage_health.json", {"stage_id": "05", "status": "failed", "error": "413"})
    s = worker.job_status(d)
    assert s["state"] == "failed"
    assert s["error"] == "05: 413"


def test_completed_run_is_done(tmp_path: Path) -> None:
    d = _job(tmp_path)
    _write(d / "exit_code", "0\n")
    _write(d / "out" / "pipeline_summary.json", {"final_status": "done", "stages_failed": 0})
    assert worker.job_status(d)["state"] == "done"


def test_gate_waits_until_answered(tmp_path: Path) -> None:
    d = _job(tmp_path)
    _write(d / "out" / "hitl" / "waiting.json", {"stage": 9})
    assert worker.job_status(d)["state"] == "waiting"
    _write(d / "out" / "hitl" / "response.json", {"action": "approve"})
    assert worker.job_status(d)["state"] == "running"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(worker, "RUNS", tmp_path)
    monkeypatch.setenv("ARC_WORKER_TOKEN", "t")
    return TestClient(worker.app)


def test_token_and_path_guards(client: TestClient, tmp_path: Path) -> None:
    assert client.get("/jobs/j1").status_code == 401
    auth = {"Authorization": "Bearer t"}
    assert client.get("/jobs/..%2Fetc", headers=auth).status_code in (400, 404)
    _job(tmp_path)
    assert client.get("/jobs/j1/file", params={"path": "../job.json"}, headers=auth).status_code == 404
    assert client.post("/jobs/j1/response", json={"action": "approve"}, headers=auth).status_code == 409


def test_stages_report_progress_decisions_and_retries(tmp_path: Path) -> None:
    out = _job(tmp_path) / "out"
    _write(out / "stage-02" / "stage_health.json", {"status": "done", "duration_sec": 4.3})
    _write(out / "stage-02" / "decision.json", {"decision": "proceed"})
    _write(out / "stage-02" / "topic_evaluation.json", {"overall": 6, "suggestion": "broaden"})
    _write(out / "stage-02" / "problem_tree.md", "tree")
    _write(out / "stage-13" / "stage_health.json", {"status": "failed", "error": "NaN loss"})
    _write(out / "stage-13_r1" / "stage_health.json", {"status": "done", "duration_sec": 30})
    _write(out / "stage-13_r1" / "decision.json", {"decision": "refine"})
    r = worker.run_stages(out)
    assert r["topic_evaluation"]["overall"] == 6
    by = {s["stage"]: s for s in r["stages"]}
    assert by[2]["artifacts"] == ["stage-02/problem_tree.md", "stage-02/topic_evaluation.json"]
    assert (by[13]["attempts"], by[13]["status"], by[13]["decision"]) == (2, "done", "refine")
