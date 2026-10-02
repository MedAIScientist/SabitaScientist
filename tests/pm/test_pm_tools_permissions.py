"""The agent's PM tools act as the signed-in user and must enforce project membership.

Before this, any authenticated user could read or write any project through the
copilot by passing its id, although the REST API returns 404 to non-members.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.experiments import create_experiment
from EvoScientist.pm.crud.projects import add_member, create_project
from EvoScientist.pm.crud.tasks import list_tasks
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm import agent_tools as t


@pytest.fixture
def world(tmp_db: Path):
    """An owner's project, plus a viewer member and an outsider."""
    owner = create_user(tmp_db, username="owner", password_hash=hash_password("p"))
    viewer = create_user(tmp_db, username="viewer", password_hash=hash_password("p"))
    outsider = create_user(tmp_db, username="outsider", password_hash=hash_password("p"))
    project = create_project(tmp_db, name="Secret study", created_by=owner.id, description="retina cohort")
    add_member(tmp_db, project.id, viewer.id, "viewer")
    exp = create_experiment(tmp_db, project_id=project.id, name="Baseline run", created_by=owner.id)
    return {"db": tmp_db, "owner": owner, "viewer": viewer, "outsider": outsider, "project": project, "exp": exp}


def _as(user) -> None:
    t.current_user_id.set(user.id)


def test_outsider_cannot_read_or_write_a_project(world) -> None:
    pid = world["project"].id
    _as(world["outsider"])
    for result in (
        t.pm_get_project.invoke({"project_id": pid}),
        t.pm_list_tasks.invoke({"project_id": pid}),
        t.pm_list_experiments.invoke({"project_id": pid}),
        t.pm_create_task.invoke({"project_id": pid, "title": "sneaky"}),
        t.pm_create_experiment.invoke({"project_id": pid, "name": "sneaky"}),
        t.pm_list_experiment_entries.invoke({"experiment_id": world["exp"].id}),
        t.pm_add_experiment_entry.invoke({"experiment_id": world["exp"].id, "entry_type": "note", "title": "x"}),
    ):
        assert result.startswith("Error:"), result
        assert "Secret study" not in result
    assert list_tasks(world["db"], pid) == []


def test_viewer_can_read_but_not_write(world) -> None:
    pid = world["project"].id
    _as(world["viewer"])
    assert "Secret study" in t.pm_get_project.invoke({"project_id": pid})
    denied = t.pm_create_task.invoke({"project_id": pid, "title": "x"})
    assert denied.startswith("Error:") and "viewer" in denied
    assert list_tasks(world["db"], pid) == []


def test_owner_can_write_and_legacy_critical_priority_is_folded(world) -> None:
    pid = world["project"].id
    _as(world["owner"])
    result = t.pm_create_task.invoke({"project_id": pid, "title": "Collect scans", "priority": "critical"})
    assert result.startswith("Created task")
    (task,) = list_tasks(world["db"], pid)
    assert task.priority == "high"
    assert t.pm_create_task.invoke({"project_id": pid, "title": "x", "priority": "urgent"}).startswith("Error:")


def test_global_search_only_covers_the_callers_projects(world) -> None:
    _as(world["outsider"])
    assert "Secret study" not in t.pm_global_search.invoke({"query": "secret"})
    _as(world["owner"])
    found = t.pm_global_search.invoke({"query": "secret"})
    assert "Secret study" in found
    assert "Baseline run" in t.pm_global_search.invoke({"query": "baseline"})


def test_publication_cannot_be_attached_to_a_foreign_project(world) -> None:
    _as(world["outsider"])
    result = t.pm_create_publication.invoke({"title": "Paper", "project_id": world["project"].id})
    assert result.startswith("Error:")


def test_owner_can_add_an_experiment_entry(world) -> None:
    """pm_add_experiment_entry used to pass type= to create_entry and always raised."""
    from EvoScientist.pm.crud.experiment_entries import list_entries

    _as(world["owner"])
    result = t.pm_add_experiment_entry.invoke(
        {"experiment_id": world["exp"].id, "entry_type": "result", "title": "AUC 0.91", "body": "fold 1"}
    )
    assert result.startswith("Added result"), result
    assert [e.title for e in list_entries(world["db"], world["exp"].id)] == ["AUC 0.91"]
