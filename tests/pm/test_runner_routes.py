# tests/pm/test_runner_routes.py
"""Tests for the runner service routes."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def runner_client():
    from EvoScientist.pm.runner.main import create_runner_app
    return TestClient(create_runner_app())


def test_start_run_returns_202(runner_client):
    with patch("EvoScientist.pm.runner.routes.runs.agent_runner.start_run", new=AsyncMock()):
        resp = runner_client.post("/runs", json={
            "run_id": "abc123",
            "agent_type": "research",
            "prompt": "Find protocols",
            "workspace_dir": "/tmp/test_workspace",
        })
    assert resp.status_code == 202
    assert resp.json() == {"run_id": "abc123"}


def test_start_run_invalid_agent_type(runner_client):
    resp = runner_client.post("/runs", json={
        "run_id": "abc123",
        "agent_type": "invalid",
        "prompt": "p",
        "workspace_dir": "/tmp",
    })
    assert resp.status_code == 422


def test_cancel_run_returns_204_when_found(runner_client):
    with patch("EvoScientist.pm.runner.routes.runs.agent_runner.cancel", new=AsyncMock(return_value=True)):
        resp = runner_client.delete("/runs/abc123")
    assert resp.status_code == 204


def test_cancel_run_returns_404_when_not_found(runner_client):
    with patch("EvoScientist.pm.runner.routes.runs.agent_runner.cancel", new=AsyncMock(return_value=False)):
        resp = runner_client.delete("/runs/missing")
    assert resp.status_code == 404
