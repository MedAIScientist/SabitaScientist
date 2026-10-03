"""Tests for the link between project tasks and the weekly update.

The behaviour under test is ownership: the task owns status, the student owns the
narrative, and neither is allowed to overwrite the other. A report that was already
submitted is a closed record and must never be rewritten.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gazzali.api.app import create_app
from gazzali.auth import hash_password
from gazzali.crud.users import create_user


def _monday(offset_weeks: int = 0) -> str:
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset_weeks)
    return monday.isoformat()


@pytest.fixture
def client(tmp_db: Path) -> TestClient:
    """An app seeded with an admin, a student, a second student and a project."""
    create_user(tmp_db, "admin", hash_password("pw"), is_admin=True, role="admin")
    stud = create_user(tmp_db, "stud", hash_password("pw"), role="student")
    other = create_user(tmp_db, "other", hash_password("pw"), role="student")

    c = TestClient(create_app(tmp_db))

    def _login(username: str) -> str:
        r = c.post("/api/v1/auth/login", json={"username": username, "password": "pw"})
        assert r.status_code == 200, r.text
        return r.json()["token"]

    c.admin_token = _login("admin")
    c.stud_token = _login("stud")
    c.other_token = _login("other")
    c.stud_id = stud.id
    c.other_id = other.id
    return c


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _project(client: TestClient, token: str, name: str = "Imaging study") -> str:
    resp = client.post("/api/v1/projects", json={"name": name}, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _add_member(client: TestClient, token: str, project_id: str, user_id: str, role: str = "editor") -> None:
    resp = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": user_id, "role": role},
        headers=_h(token),
    )
    assert resp.status_code in (200, 201), resp.text


def _task(
    client: TestClient,
    token: str,
    project_id: str,
    *,
    title: str = "Denoise cohort",
    assignee_id: str,
    status: str = "todo",
    deadline: str | None = None,
) -> str:
    resp = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": title, "assignee_id": assignee_id, "status": status, "deadline": deadline},
        headers=_h(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _week_with_task(client: TestClient, **task_kwargs) -> tuple[str, str, str]:
    """A project owned by the student with one assigned task, plus that week's report."""
    project_id = _project(client, client.stud_token)
    task_id = _task(
        client, client.stud_token, project_id, assignee_id=client.stud_id, **task_kwargs
    )
    report = client.post(
        f"/api/v1/supervision/weekly/current?week={_monday()}", headers=_h(client.stud_token)
    )
    assert report.status_code == 200, report.text
    return project_id, task_id, report.json()["id"]


def _items(client: TestClient, report_id: str) -> list[dict]:
    resp = client.get(f"/api/v1/supervision/reports/{report_id}", headers=_h(client.stud_token))
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


def _item_for(report_items: list[dict], task_id: str) -> dict | None:
    return next((i for i in report_items if i["task_id"] == task_id), None)


# ── The relationship exists ──────────────────────────────────────────────────


def test_opening_the_week_pulls_assigned_tasks_into_the_update(client: TestClient) -> None:
    project_id, task_id, report_id = _week_with_task(client, title="Segment lesions")

    item = _item_for(_items(client, report_id), task_id)
    assert item is not None, "the assigned task did not appear in the weekly update"
    assert item["item_title"] == "Segment lesions"
    assert item["item_kind"] == "task"
    assert item["status"] == "planned"


def test_a_task_assigned_to_someone_else_stays_out(client: TestClient) -> None:
    project_id = _project(client, client.stud_token)
    _add_member(client, client.stud_token, project_id, client.other_id)
    mine = _task(client, client.stud_token, project_id, title="Mine", assignee_id=client.stud_id)
    theirs = _task(client, client.stud_token, project_id, title="Theirs", assignee_id=client.other_id)

    report = client.post(
        f"/api/v1/supervision/weekly/current?week={_monday()}", headers=_h(client.stud_token)
    ).json()
    items = _items(client, report["id"])
    assert _item_for(items, mine) is not None
    assert _item_for(items, theirs) is None


def test_a_task_from_a_project_the_student_left_stays_out(client: TestClient) -> None:
    """A task left behind in a project the student was removed from is not their work."""
    project_id = _project(client, client.admin_token)
    _add_member(client, client.admin_token, project_id, client.stud_id)
    task_id = _task(client, client.admin_token, project_id, assignee_id=client.stud_id)

    removed = client.delete(
        f"/api/v1/projects/{project_id}/members/{client.stud_id}", headers=_h(client.admin_token)
    )
    assert removed.status_code in (200, 204), removed.text

    report = client.post(
        f"/api/v1/supervision/weekly/current?week={_monday()}", headers=_h(client.stud_token)
    ).json()
    assert _item_for(_items(client, report["id"]), task_id) is None


def test_open_tasks_always_appear_and_finished_ones_only_if_recent(client: TestClient) -> None:
    """The week reports current work plus what was actually finished this week —
    never every task the student has ever closed."""
    project_id, open_task, report_id = _week_with_task(client, title="Still open")
    done_this_week = _task(
        client, client.stud_token, project_id, title="Finished now", assignee_id=client.stud_id
    )
    client.put(
        f"/api/v1/projects/{project_id}/tasks/{done_this_week}",
        json={"status": "done"},
        headers=_h(client.stud_token),
    )

    report = client.post(
        f"/api/v1/supervision/weekly/current?week={_monday()}", headers=_h(client.stud_token)
    ).json()
    items = _items(client, report["id"])
    assert _item_for(items, open_task) is not None
    assert _item_for(items, done_this_week) is not None, "work finished this week must be reportable"


def test_a_task_finished_before_this_week_is_not_re_reported(client: TestClient, tmp_db: Path) -> None:
    import sqlite3

    project_id = _project(client, client.stud_token)
    old_task = _task(client, client.stud_token, project_id, title="Old work", assignee_id=client.stud_id)
    long_ago = (datetime.now(UTC) - timedelta(days=21)).isoformat()
    conn = sqlite3.connect(tmp_db)
    conn.execute("UPDATE tasks SET status='done', updated_at=? WHERE id=?", (long_ago, old_task))
    conn.commit()
    conn.close()

    report = client.post(
        f"/api/v1/supervision/weekly/current?week={_monday()}", headers=_h(client.stud_token)
    ).json()
    assert _item_for(_items(client, report["id"]), old_task) is None


def test_marking_a_task_done_from_the_weekly_page_moves_the_task_too(client: TestClient) -> None:
    project_id, task_id, report_id = _week_with_task(client, title="Draft methods")

    resp = client.put(
        f"/api/v1/supervision/weekly/tasks/{task_id}?week={_monday()}",
        json={"status": "done"},
        headers=_h(client.stud_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["task"]["status"] == "done"
    assert body["report_locked"] is False

    item = _item_for(_items(client, report_id), task_id)
    assert item["status"] == "done"
    assert item["progress_pct"] == 100

    # …and the task itself moved, so the board cannot disagree with the report.
    task = client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}", headers=_h(client.stud_token)
    )
    assert task.json()["status"] == "done"


def test_starting_a_task_keeps_a_progress_the_student_typed(client: TestClient) -> None:
    """50% is not implied by 'in progress', so a typed number must survive."""
    project_id, task_id, report_id = _week_with_task(client, title="Tune model")
    item = _item_for(_items(client, report_id), task_id)

    client.put(
        f"/api/v1/supervision/reports/{report_id}/items",
        json={"item_id": item["id"], "item_title": item["item_title"], "task_id": task_id, "progress_pct": 20},
        headers=_h(client.stud_token),
    )
    client.put(
        f"/api/v1/supervision/weekly/tasks/{task_id}?week={_monday()}",
        json={"status": "in_progress"},
        headers=_h(client.stud_token),
    )
    after = _item_for(_items(client, report_id), task_id)
    assert after["status"] == "in_progress"
    assert after["progress_pct"] == 20


def test_the_narrative_survives_a_status_refresh(client: TestClient) -> None:
    """Reconciliation refreshes derived fields only; what the student wrote stays."""
    project_id, task_id, report_id = _week_with_task(client, title="Write intro")

    client.put(
        f"/api/v1/supervision/weekly/tasks/{task_id}?week={_monday()}",
        json={"what_changed": "drafted the opening paragraph", "blocker": "needs the cohort numbers"},
        headers=_h(client.stud_token),
    )
    client.put(
        f"/api/v1/supervision/weekly/tasks/{task_id}?week={_monday()}",
        json={"status": "in_progress"},
        headers=_h(client.stud_token),
    )

    item = _item_for(_items(client, report_id), task_id)
    assert item["what_changed"] == "drafted the opening paragraph"
    assert item["blocker"] == "needs the cohort numbers"


def test_needs_help_can_be_raised_from_the_dashboard(client: TestClient) -> None:
    project_id, task_id, report_id = _week_with_task(client, title="Access the dataset")

    resp = client.put(
        f"/api/v1/supervision/weekly/tasks/{task_id}?week={_monday()}",
        json={"needs_help": True},
        headers=_h(client.stud_token),
    )
    assert resp.status_code == 200, resp.text
    assert _item_for(_items(client, report_id), task_id)["needs_help"] is True


def test_a_submitted_week_is_never_rewritten(client: TestClient) -> None:
    """A supervisor already read that week: only the task may move afterwards."""
    project_id, task_id, report_id = _week_with_task(client, title="Submit the abstract")
    submitted = client.post(
        f"/api/v1/supervision/reports/{report_id}/submit", headers=_h(client.stud_token)
    )
    assert submitted.status_code == 200, submitted.text

    before = _item_for(_items(client, report_id), task_id)
    resp = client.put(
        f"/api/v1/supervision/weekly/tasks/{task_id}?week={_monday()}",
        json={"status": "done", "what_changed": "rewritten history"},
        headers=_h(client.stud_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["report_locked"] is True
    assert resp.json()["task"]["status"] == "done"

    after = _item_for(_items(client, report_id), task_id)
    assert after["what_changed"] == before["what_changed"]
    assert after["status"] == before["status"]


def test_the_task_list_is_read_only(client: TestClient, tmp_db: Path) -> None:
    """Looking at the dashboard must not create a report for the week."""
    import sqlite3

    project_id = _project(client, client.stud_token)
    _task(client, client.stud_token, project_id, assignee_id=client.stud_id)

    resp = client.get(
        f"/api/v1/supervision/weekly/tasks?week={_monday()}", headers=_h(client.stud_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["report_id"] is None
    assert len(body["tasks"]) == 1
    assert body["tasks"][0]["item_id"] is None

    conn = sqlite3.connect(tmp_db)
    reports = conn.execute("SELECT COUNT(*) FROM weekly_reports").fetchone()[0]
    conn.close()
    assert reports == 0


def test_the_task_list_reports_what_the_update_already_says(client: TestClient) -> None:
    project_id, task_id, report_id = _week_with_task(client, title="Review figures")
    client.put(
        f"/api/v1/supervision/weekly/tasks/{task_id}?week={_monday()}",
        json={"needs_help": True},
        headers=_h(client.stud_token),
    )

    body = client.get(
        f"/api/v1/supervision/weekly/tasks?week={_monday()}", headers=_h(client.stud_token)
    ).json()
    row = next(t for t in body["tasks"] if t["id"] == task_id)
    assert row["item_id"] is not None
    assert row["item_needs_help"] is True
    assert row["report_id"] == report_id
    assert row["report_status"] == "draft"


def test_a_student_cannot_move_someone_elses_task(client: TestClient) -> None:
    project_id = _project(client, client.admin_token)
    _add_member(client, client.admin_token, project_id, client.stud_id)
    task_id = _task(client, client.admin_token, project_id, assignee_id=client.other_id)

    resp = client.put(
        f"/api/v1/supervision/weekly/tasks/{task_id}?week={_monday()}",
        json={"status": "done"},
        headers=_h(client.stud_token),
    )
    assert resp.status_code == 403


def test_weekly_tasks_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/supervision/weekly/tasks").status_code == 401
    assert client.put("/api/v1/supervision/weekly/tasks/whatever", json={}).status_code == 401


def test_reconciling_twice_does_not_duplicate_items(client: TestClient) -> None:
    project_id, task_id, report_id = _week_with_task(client, title="Idempotent work")
    client.post(f"/api/v1/supervision/weekly/current?week={_monday()}", headers=_h(client.stud_token))
    client.post(f"/api/v1/supervision/weekly/current?week={_monday()}", headers=_h(client.stud_token))

    matching = [i for i in _items(client, report_id) if i["task_id"] == task_id]
    assert len(matching) == 1
