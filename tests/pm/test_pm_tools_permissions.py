"""The agent's PM tools act as the signed-in user and must enforce project membership.

Before this, any authenticated user could read or write any project through the
copilot by passing its id, although the REST API returns 404 to non-members.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gazzali import agent_tools as t
from gazzali.auth import hash_password
from gazzali.crud.experiments import create_experiment
from gazzali.crud.projects import add_member, create_project
from gazzali.crud.tasks import list_tasks
from gazzali.crud.users import create_user


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
    from gazzali.crud.experiment_entries import list_entries

    _as(world["owner"])
    result = t.pm_add_experiment_entry.invoke(
        {"experiment_id": world["exp"].id, "entry_type": "result", "title": "AUC 0.91", "body": "fold 1"}
    )
    assert result.startswith("Added result"), result
    assert [e.title for e in list_entries(world["db"], world["exp"].id)] == ["AUC 0.91"]


# ── Creating a project in a lab: the copilot obeys the API's rule ─────────────


@pytest.fixture
def lab_world(tmp_db: Path):
    from gazzali.crud.labs import add_member as add_lab_member
    from gazzali.crud.labs import create_lab

    pi = create_user(tmp_db, username="pi", password_hash=hash_password("p"))
    member = create_user(tmp_db, username="member", password_hash=hash_password("p"))
    outsider = create_user(tmp_db, username="outsider", password_hash=hash_password("p"))
    admin = create_user(tmp_db, username="root", password_hash=hash_password("p"), is_admin=True)
    lab = create_lab(tmp_db, name="Bone Lab", pi_id=pi.id)
    add_lab_member(tmp_db, lab.id, pi.id, "pi")
    add_lab_member(tmp_db, lab.id, member.id, "ms")
    return {"db": tmp_db, "lab": lab, "member": member, "outsider": outsider, "admin": admin}


def _projects_in(db: Path, lab_id: str) -> list[str]:
    import sqlite3

    con = sqlite3.connect(db)
    try:
        return [r[0] for r in con.execute("SELECT name FROM projects WHERE lab_id = ?", (lab_id,))]
    finally:
        con.close()


def test_an_outsider_cannot_put_a_project_in_a_lab_through_the_copilot(lab_world) -> None:
    """The bypass: POST /projects refuses an outsider's lab_id, but the copilot's approve path
    ran pm_create_project on the client's own word with no membership check."""
    _as(lab_world["outsider"])
    result = t.pm_create_project.invoke({"name": "Planted", "lab_id": lab_world["lab"].id})
    assert result.startswith("Error:")
    assert "member of the lab" in result
    assert _projects_in(lab_world["db"], lab_world["lab"].id) == []


@pytest.mark.parametrize("who", ["member", "admin"])
def test_a_member_or_an_admin_still_creates_one_through_the_copilot(lab_world, who) -> None:
    _as(lab_world[who])
    result = t.pm_create_project.invoke({"name": f"By {who}", "lab_id": lab_world["lab"].id})
    assert not result.startswith("Error:"), result
    assert _projects_in(lab_world["db"], lab_world["lab"].id) == [f"By {who}"]



# ── the lab a copilot-created project lands in (2026-10-17) ─────────────────
#
# student2's project was created through the copilot with no lab named, so it landed outside any
# lab — and a project's lab can never be changed. The copilot now chooses the way the New-project
# screen does.


@pytest.fixture
def two_labs(lab_world):
    from gazzali.crud.labs import add_member as add_lab_member
    from gazzali.crud.labs import create_lab

    other = create_lab(lab_world["db"], name="Second Lab", pi_id=lab_world["lab"].pi_id)
    add_lab_member(lab_world["db"], other.id, lab_world["member"].id, "phd")
    return {**lab_world, "other": other}


def test_a_member_of_one_lab_gets_that_lab_without_naming_it(lab_world) -> None:
    _as(lab_world["member"])
    result = t.pm_create_project.invoke({"name": "Ankle study"})
    assert f"in lab '{lab_world['lab'].name}'" in result
    assert _projects_in(lab_world["db"], lab_world["lab"].id) == ["Ankle study"]


def test_a_member_of_several_labs_is_asked_which_and_nothing_is_created(two_labs) -> None:
    _as(two_labs["member"])
    result = t.pm_create_project.invoke({"name": "Undecided"})
    assert result.startswith("Which lab should this project belong to?")
    assert "Second Lab" in result
    assert _projects_in(two_labs["db"], two_labs["lab"].id) == []
    assert _projects_in(two_labs["db"], two_labs["other"].id) == []


def test_a_lab_named_by_its_name_is_found(two_labs) -> None:
    _as(two_labs["member"])
    result = t.pm_create_project.invoke({"name": "Named", "lab_id": "second lab"})
    assert "in lab 'Second Lab'" in result
    assert _projects_in(two_labs["db"], two_labs["other"].id) == ["Named"]


def test_an_unknown_lab_is_an_error_not_a_silent_no_lab(lab_world) -> None:
    _as(lab_world["member"])
    result = t.pm_create_project.invoke({"name": "Typo", "lab_id": "neruo lab"})
    assert result.startswith("Error: there is no lab called")
    assert "Nothing was created" in result
    assert _projects_in(lab_world["db"], lab_world["lab"].id) == []


def test_no_lab_is_honoured_only_when_asked_for(lab_world) -> None:
    _as(lab_world["member"])
    result = t.pm_create_project.invoke({"name": "Solo", "lab_id": "none"})
    assert "outside any lab" in result
    assert _projects_in(lab_world["db"], lab_world["lab"].id) == []
