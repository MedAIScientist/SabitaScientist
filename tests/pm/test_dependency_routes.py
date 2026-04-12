"""Tests for task dependency routes and TaskResponse extended fields."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_project(client, admin_token, name="Dep Test Project"):
    resp = client.post(
        "/api/v1/projects",
        json={"name": name},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_task(client, admin_token, project_id, title="Task"):
    resp = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": title},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _add_dep(client, admin_token, project_id, task_id, depends_on_id, dep_type="hard"):
    return client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/dependencies",
        json={"depends_on_id": depends_on_id, "dep_type": dep_type},
        headers={"Authorization": f"Bearer {admin_token}"},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_add_dependency(client, admin_token) -> None:
    """POST → 201, returned fields match."""
    project_id = _create_project(client, admin_token)
    task_a = _create_task(client, admin_token, project_id, "Task A")
    task_b = _create_task(client, admin_token, project_id, "Task B")

    resp = _add_dep(client, admin_token, project_id, task_b, task_a)
    assert resp.status_code == 201
    data = resp.json()
    assert data["task_id"] == task_b
    assert data["depends_on_id"] == task_a
    assert data["dep_type"] == "hard"
    assert "created_at" in data
    assert "created_by" in data


def test_add_dependency_self(client, admin_token) -> None:
    """POST where task_id == depends_on_id → 400."""
    project_id = _create_project(client, admin_token)
    task_a = _create_task(client, admin_token, project_id, "Self Task")

    resp = _add_dep(client, admin_token, project_id, task_a, task_a)
    assert resp.status_code == 400


def test_add_dependency_cycle(client, admin_token) -> None:
    """POST that would create a cycle → 400."""
    project_id = _create_project(client, admin_token)
    task_a = _create_task(client, admin_token, project_id, "Task A")
    task_b = _create_task(client, admin_token, project_id, "Task B")

    # A depends on B
    r1 = _add_dep(client, admin_token, project_id, task_a, task_b)
    assert r1.status_code == 201

    # B depends on A → cycle
    resp = _add_dep(client, admin_token, project_id, task_b, task_a)
    assert resp.status_code == 400


def test_add_dependency_duplicate(client, admin_token) -> None:
    """POST same dependency twice → 400."""
    project_id = _create_project(client, admin_token)
    task_a = _create_task(client, admin_token, project_id, "Task A")
    task_b = _create_task(client, admin_token, project_id, "Task B")

    r1 = _add_dep(client, admin_token, project_id, task_b, task_a)
    assert r1.status_code == 201

    resp = _add_dep(client, admin_token, project_id, task_b, task_a)
    assert resp.status_code == 400


def test_remove_dependency(client, admin_token) -> None:
    """DELETE existing dependency → 204."""
    project_id = _create_project(client, admin_token)
    task_a = _create_task(client, admin_token, project_id, "Task A")
    task_b = _create_task(client, admin_token, project_id, "Task B")

    _add_dep(client, admin_token, project_id, task_b, task_a)

    resp = client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_b}/dependencies/{task_a}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204


def test_remove_dependency_not_found(client, admin_token) -> None:
    """DELETE non-existent dependency → 404."""
    project_id = _create_project(client, admin_token)
    task_a = _create_task(client, admin_token, project_id, "Task A")
    task_b = _create_task(client, admin_token, project_id, "Task B")

    resp = client.delete(
        f"/api/v1/projects/{project_id}/tasks/{task_b}/dependencies/{task_a}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_list_dependencies(client, admin_token) -> None:
    """GET list returns DependenciesListResponse structure with both directions."""
    project_id = _create_project(client, admin_token)
    task_a = _create_task(client, admin_token, project_id, "Task A")
    task_b = _create_task(client, admin_token, project_id, "Task B")
    task_c = _create_task(client, admin_token, project_id, "Task C")

    # B depends on A (A is a prerequisite of B)
    _add_dep(client, admin_token, project_id, task_b, task_a)
    # C depends on B (B is a prerequisite of C)
    _add_dep(client, admin_token, project_id, task_c, task_b)

    # List dependencies for task_b:
    # dependencies = [task_a] (what B depends on)
    # dependents = [task_c] (what depends on B)
    resp = client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_b}/dependencies",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "dependencies" in data
    assert "dependents" in data
    assert len(data["dependencies"]) == 1
    assert data["dependencies"][0]["depends_on_id"] == task_a
    assert len(data["dependents"]) == 1
    assert data["dependents"][0]["task_id"] == task_c


def test_task_response_has_blocked_by(client, admin_token) -> None:
    """GET /tasks/{id} response includes blocked_by list."""
    project_id = _create_project(client, admin_token)
    task_a = _create_task(client, admin_token, project_id, "Blocker")
    task_b = _create_task(client, admin_token, project_id, "Blocked")

    # B depends on A (hard)
    _add_dep(client, admin_token, project_id, task_b, task_a, dep_type="hard")

    resp = client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_b}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "blocked_by" in data
    assert task_a in data["blocked_by"]


def test_task_response_has_phase_id(client, admin_token) -> None:
    """GET /tasks/{id} response includes phase_id field (None when no phase assigned)."""
    project_id = _create_project(client, admin_token)
    task_id = _create_task(client, admin_token, project_id, "Phase Task")

    resp = client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "phase_id" in data
    assert data["phase_id"] is None


def test_task_response_blocked_by_soft_deps_excluded(client, admin_token) -> None:
    """blocked_by only includes hard dependencies, not soft ones."""
    project_id = _create_project(client, admin_token)
    task_a = _create_task(client, admin_token, project_id, "Soft Dep")
    task_b = _create_task(client, admin_token, project_id, "Dependent Task")

    # B softly depends on A
    _add_dep(client, admin_token, project_id, task_b, task_a, dep_type="soft")

    resp = client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_b}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "blocked_by" in data
    assert task_a not in data["blocked_by"]
    assert data["blocked_by"] == []
