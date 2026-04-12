"""Tests for /projects/{project_id}/phases routes."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_project(client, admin_token, name="Test Project"):
    resp = client.post(
        "/api/v1/projects",
        json={"name": name},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_task(client, admin_token, project_id, title="Test Task"):
    resp = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": title},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_phase(client, admin_token, project_id, name="Phase 1", position=0):
    resp = client.post(
        f"/api/v1/projects/{project_id}/phases",
        json={"name": name, "position": position},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_phase(client, admin_token) -> None:
    project_id = _create_project(client, admin_token)
    resp = _create_phase(client, admin_token, project_id, name="Sprint 1", position=0)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Sprint 1"
    assert data["position"] == 0
    assert data["project_id"] == project_id
    assert data["color"] == "#6366f1"
    assert "id" in data
    assert "created_at" in data
    assert "created_by" in data


def test_list_phases(client, admin_token) -> None:
    project_id = _create_project(client, admin_token)
    _create_phase(client, admin_token, project_id, name="Phase A", position=1)
    _create_phase(client, admin_token, project_id, name="Phase B", position=0)

    resp = client.get(
        f"/api/v1/projects/{project_id}/phases",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    phases = resp.json()
    assert len(phases) == 2
    # Ordered by position
    assert phases[0]["position"] == 0
    assert phases[1]["position"] == 1
    assert phases[0]["name"] == "Phase B"
    assert phases[1]["name"] == "Phase A"


def test_get_phase(client, admin_token) -> None:
    project_id = _create_project(client, admin_token)
    create_resp = _create_phase(client, admin_token, project_id, name="My Phase")
    phase_id = create_resp.json()["id"]

    resp = client.get(
        f"/api/v1/projects/{project_id}/phases/{phase_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == phase_id
    assert data["name"] == "My Phase"


def test_get_phase_not_found(client, admin_token) -> None:
    project_id = _create_project(client, admin_token)
    resp = client.get(
        f"/api/v1/projects/{project_id}/phases/nonexistent-id",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_update_phase_name(client, admin_token) -> None:
    project_id = _create_project(client, admin_token)
    create_resp = _create_phase(client, admin_token, project_id, name="Old Name")
    phase_id = create_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/projects/{project_id}/phases/{phase_id}",
        json={"name": "New Name"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["id"] == phase_id


def test_delete_phase(client, admin_token) -> None:
    project_id = _create_project(client, admin_token)
    create_resp = _create_phase(client, admin_token, project_id, name="To Delete")
    phase_id = create_resp.json()["id"]

    resp = client.delete(
        f"/api/v1/projects/{project_id}/phases/{phase_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204

    # Confirm it's gone
    get_resp = client.get(
        f"/api/v1/projects/{project_id}/phases/{phase_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_resp.status_code == 404


def test_delete_phase_not_found(client, admin_token) -> None:
    project_id = _create_project(client, admin_token)
    resp = client.delete(
        f"/api/v1/projects/{project_id}/phases/nonexistent-id",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_assign_task_to_phase(client, admin_token) -> None:
    project_id = _create_project(client, admin_token)
    task_id = _create_task(client, admin_token, project_id)
    create_resp = _create_phase(client, admin_token, project_id, name="Active Phase")
    phase_id = create_resp.json()["id"]

    resp = client.post(
        f"/api/v1/projects/{project_id}/phases/{phase_id}/assign-task",
        json={"task_id": task_id, "phase_id": phase_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
