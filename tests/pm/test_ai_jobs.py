"""Background AI jobs end in a result link or a readable error, never in silence."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from EvoScientist.pm.api.routes import drafting
from EvoScientist.pm.crud.ai_jobs import AiJobError

# drafting.httpx *is* the httpx module, so patching it is global: keep the real class.
_REAL_CLIENT = httpx.AsyncClient


def _client_with(handler):
    def factory(*args, **kwargs):
        return _REAL_CLIENT(*args, **{**kwargs, "transport": httpx.MockTransport(handler)})
    return factory


def _fake_runner(events: list[dict], start_status: int = 202):
    """An httpx transport that behaves like the agent runner (POST /runs answers 202)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/runs":
            return httpx.Response(start_status, json={"run_id": "r1"})
        body = "".join(f"data: {json.dumps(e)}\n\n" for e in events)
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    return _client_with(handler)


def _run(coro):
    return asyncio.run(coro)


def test_runner_202_is_success(monkeypatch, tmp_path) -> None:
    """The runner answers 202; treating only 200 as success discarded every result."""
    events = [{"type": "token", "data": "H1: "}, {"type": "token", "data": "x"}, {"type": "status", "data": "done"}]
    monkeypatch.setattr(drafting.httpx, "AsyncClient", _fake_runner(events))
    assert _run(drafting._run_agent_and_get_output("r1", "p", str(tmp_path))) == "H1: x"


def test_runner_errors_become_readable_messages(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(drafting.httpx, "AsyncClient", _fake_runner(
        [{"type": "error", "data": "GROQ_API_KEY environment variable is required"}]))
    with pytest.raises(AiJobError, match="GROQ_API_KEY"):
        _run(drafting._run_agent_and_get_output("r1", "p", str(tmp_path)))

    monkeypatch.setattr(drafting.httpx, "AsyncClient", _fake_runner([], start_status=503))
    with pytest.raises(AiJobError, match="HTTP 503"):
        _run(drafting._run_agent_and_get_output("r1", "p", str(tmp_path)))


def test_unreachable_runner_is_reported(monkeypatch, tmp_path) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(drafting.httpx, "AsyncClient", _client_with(down))
    with pytest.raises(AiJobError, match="not reachable"):
        _run(drafting._run_agent_and_get_output("r1", "p", str(tmp_path)))


def _project(client, token) -> str:
    return client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {token}"}).json()["id"]


def test_finished_job_links_to_its_result(client, admin_token, monkeypatch) -> None:
    h = {"Authorization": f"Bearer {admin_token}"}
    pid = _project(client, admin_token)

    async def fake_output(*args, **kwargs):
        return "1. Retinal thickness predicts progression."

    monkeypatch.setattr(drafting, "_run_agent_and_get_output", fake_output)
    started = client.post(f"/api/v1/projects/{pid}/generate-hypothesis", json={"topic": "OCT"}, headers=h)
    assert started.status_code == 202
    job_id = started.json()["job_id"]

    job = client.get(f"/api/v1/ai-jobs/{job_id}", headers=h).json()
    assert job["status"] == "done"
    assert job["result_path"].startswith(f"/projects/{pid}/experiments?exp=")
    assert [j["id"] for j in client.get(f"/api/v1/ai-jobs?project_id={pid}", headers=h).json()] == [job_id]


def test_failed_job_says_why(client, admin_token, monkeypatch) -> None:
    h = {"Authorization": f"Bearer {admin_token}"}
    pid = _project(client, admin_token)

    async def failing(*args, **kwargs):
        raise AiJobError("The AI service is not reachable right now. Please try again in a minute.")

    monkeypatch.setattr(drafting, "_run_agent_and_get_output", failing)
    job_id = client.post(f"/api/v1/projects/{pid}/research-ideation", json={"topic": "OCT"}, headers=h).json()["job_id"]
    job = client.get(f"/api/v1/ai-jobs/{job_id}", headers=h).json()
    assert job["status"] == "failed"
    assert "not reachable" in job["error"]


def test_empty_output_and_unexpected_errors_fail_with_a_message(client, admin_token, monkeypatch) -> None:
    h = {"Authorization": f"Bearer {admin_token}"}
    pid = _project(client, admin_token)

    async def empty(*args, **kwargs):
        return None

    monkeypatch.setattr(drafting, "_run_agent_and_get_output", empty)
    job_id = client.post(f"/api/v1/projects/{pid}/generate-hypothesis", json={"topic": "x"}, headers=h).json()["job_id"]
    assert "no text" in client.get(f"/api/v1/ai-jobs/{job_id}", headers=h).json()["error"]

    async def boom(*args, **kwargs):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(drafting, "_run_agent_and_get_output", boom)
    job_id = client.post(f"/api/v1/projects/{pid}/generate-hypothesis", json={"topic": "x"}, headers=h).json()["job_id"]
    job = client.get(f"/api/v1/ai-jobs/{job_id}", headers=h).json()
    assert job["status"] == "failed" and "database is locked" not in job["error"]


def test_jobs_are_private_to_their_owner(client, admin_token, tmp_db, monkeypatch) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user

    async def fake_output(*args, **kwargs):
        return "ok"

    monkeypatch.setattr(drafting, "_run_agent_and_get_output", fake_output)
    pid = _project(client, admin_token)
    job_id = client.post(f"/api/v1/projects/{pid}/generate-hypothesis", json={"topic": "x"},
                         headers={"Authorization": f"Bearer {admin_token}"}).json()["job_id"]
    create_user(tmp_db, username="other", password_hash=hash_password("p"))
    other = client.post("/api/v1/auth/login", json={"username": "other", "password": "p"}).json()["token"]
    assert client.get(f"/api/v1/ai-jobs/{job_id}", headers={"Authorization": f"Bearer {other}"}).status_code == 404
    assert client.get("/api/v1/ai-jobs", headers={"Authorization": f"Bearer {other}"}).json() == []


def test_jobs_left_running_by_a_restart_are_failed(tmp_db) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.ai_jobs import create_job, fail_stale_jobs, get_job
    from EvoScientist.pm.crud.users import create_user

    user = create_user(tmp_db, username="u", password_hash=hash_password("p"))
    job = create_job(tmp_db, kind="draft-section", title="Draft", user_id=user.id)
    assert fail_stale_jobs(tmp_db) == 1
    assert "restarted" in get_job(tmp_db, job.id).error


def test_system_health_reports_the_models_in_use(client, admin_token) -> None:
    """It used to report a hard-coded 'mixtral-8x7b-32768' and the UI read a field
    (langgraph_dev) that no longer existed, which crashed Settings → Analytics."""
    from EvoScientist.pm._ai import pm_model_choice
    from EvoScientist.pm.runner.agent_runner import _get_model

    body = client.get("/api/v1/system/health", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert body["ai"]["runner_model"] == _get_model()
    assert body["ai"]["assistant_model"] == pm_model_choice()[0]
    assert isinstance(body["ai"]["runner_configured"], bool)
    assert "mixtral-8x7b-32768" not in str(body)
