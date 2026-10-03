"""Smoke tests for AI-powered endpoints.

These verify the endpoint wiring (auth, permissions, 202 accepted, background
task dispatch) without invoking a real LLM. The single agent seam
``drafting._run_agent_and_get_output`` is mocked; TestClient runs the
BackgroundTask synchronously after the response, so the mock is awaited.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

SEAM = "gazzali.api.routes.drafting._run_agent_and_get_output"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_project(client, admin_token: str) -> str:
    resp = client.post("/api/v1/projects", json={"name": "AI Host"}, headers=_auth(admin_token))
    assert resp.status_code == 201
    return resp.json()["id"]


def test_generate_hypothesis_runs_the_debate_panel(client, admin_token) -> None:
    from gazzali import _ai

    project_id = _make_project(client, admin_token)
    with patch.object(_ai, "debate", new=AsyncMock(return_value="## Synthesis\nH1: X causes Y.")) as mock_debate:
        resp = client.post(
            f"/api/v1/projects/{project_id}/generate-hypothesis",
            json={"topic": "protein folding"},
            headers=_auth(admin_token),
        )
    assert resp.status_code == 202
    assert resp.json()["status"] == "generating"
    mock_debate.assert_awaited_once()
    assert mock_debate.await_args.args[1] is _ai.HYPOTHESIS_ROLES


def test_draft_section_dispatches_agent(client, admin_token, admin_user, tmp_db) -> None:
    from gazzali.crud.publications import create_publication

    project_id = _make_project(client, admin_token)
    pub = create_publication(tmp_db, title="Paper", created_by=admin_user.id, project_id=project_id)

    with patch(SEAM, new=AsyncMock(return_value="## Abstract\nWe show...")) as mock_agent:
        resp = client.post(
            f"/api/v1/publications/{pub.id}/draft-section",
            json={"section": "abstract", "style": "concise"},
            headers=_auth(admin_token),
        )
    assert resp.status_code == 202
    assert resp.json()["section"] == "abstract"
    mock_agent.assert_awaited_once()


def test_draft_section_unknown_publication_404(client, admin_token) -> None:
    with patch(SEAM, new=AsyncMock(return_value="x")):
        resp = client.post(
            "/api/v1/publications/does-not-exist/draft-section",
            json={"section": "abstract", "style": "concise"},
            headers=_auth(admin_token),
        )
    assert resp.status_code == 404


def test_draft_section_bad_section_rejected(client, admin_token, admin_user, tmp_db) -> None:
    from gazzali.crud.publications import create_publication

    pub = create_publication(tmp_db, title="Paper", created_by=admin_user.id)
    resp = client.post(
        f"/api/v1/publications/{pub.id}/draft-section",
        json={"section": "bibliography", "style": "concise"},  # not an allowed section
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/v1/projects/p/generate-hypothesis", {"topic": "t"}),
        ("/api/v1/publications/p/draft-section", {"section": "abstract"}),
    ],
)
def test_ai_endpoints_require_auth(client, path, body) -> None:
    assert client.post(path, json=body).status_code == 401


def test_debate_runs_three_roles_then_synthesizes(monkeypatch) -> None:
    import asyncio

    from gazzali import _ai

    calls: list[str] = []

    async def fake_llm(system, user, **kw):
        calls.append(system)
        return "SYNTH" if system.startswith("You synthesize") else f"view of {system.split('.')[0]}"

    monkeypatch.setattr(_ai, "run_llm_direct_async", fake_llm)
    out = asyncio.run(_ai.debate("Is X true?", _ai.HYPOTHESIS_ROLES, "Distill hypotheses."))
    assert len(calls) == 4
    assert out.startswith("## Synthesis\n\nSYNTH")
    for role in ("Innovator", "Pragmatist", "Contrarian"):
        assert f"### {role}\nview of You are the {role}" in out
