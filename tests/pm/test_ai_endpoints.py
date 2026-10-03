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


def test_generate_hypothesis_dispatches_agent(client, admin_token) -> None:
    project_id = _make_project(client, admin_token)
    with patch(SEAM, new=AsyncMock(return_value="H1: X causes Y.")) as mock_agent:
        resp = client.post(
            f"/api/v1/projects/{project_id}/generate-hypothesis",
            json={"topic": "protein folding"},
            headers=_auth(admin_token),
        )
    assert resp.status_code == 202
    assert resp.json()["status"] == "generating"
    mock_agent.assert_awaited_once()


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
