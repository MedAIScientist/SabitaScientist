"""My open tasks across projects, for the student dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from gazzali.api.app import create_app
from gazzali.auth import hash_password
from gazzali.crud.projects import add_member, create_project
from gazzali.crud.tasks import create_task, update_task
from gazzali.crud.users import create_user


def test_my_tasks_are_open_mine_and_by_deadline(tmp_db: Path) -> None:
    me = create_user(tmp_db, "ayse", hash_password("pw123456"))
    other = create_user(tmp_db, "ali", hash_password("pw123456"))
    p1 = create_project(tmp_db, "DR", other.id)
    p2 = create_project(tmp_db, "OCT", other.id)
    left = create_project(tmp_db, "Old", other.id)
    add_member(tmp_db, p1.id, me.id, "editor")
    add_member(tmp_db, p2.id, me.id, "editor")
    late = create_task(tmp_db, p2.id, "Write methods", other.id, assignee_id=me.id, deadline="2026-10-20")
    soon = create_task(tmp_db, p1.id, "Label images", other.id, assignee_id=me.id, deadline="2026-10-05")
    create_task(tmp_db, p1.id, "No deadline", other.id, assignee_id=me.id)
    done = create_task(tmp_db, p1.id, "Finished", other.id, assignee_id=me.id)
    update_task(tmp_db, done.id, status="done")
    create_task(tmp_db, p1.id, "Not mine", other.id, assignee_id=other.id)
    create_task(tmp_db, left.id, "Removed project", other.id, assignee_id=me.id)
    c = TestClient(create_app(tmp_db))
    tok = c.post("/api/v1/auth/login", json={"username": "ayse", "password": "pw123456"}).json()["token"]
    rows = c.get("/api/v1/me/tasks", headers={"Authorization": f"Bearer {tok}"}).json()
    assert [r["title"] for r in rows] == ["Label images", "Write methods", "No deadline"]
    assert rows[0]["project_name"] == "DR"
    assert {soon.id, late.id} <= {r["id"] for r in rows}


def test_my_supervisor_includes_the_name(tmp_db: Path) -> None:
    from gazzali.crud.supervision import assign_supervisor

    prof = create_user(tmp_db, "kaya", hash_password("pw123456"), email="kaya@medipol.edu.tr")
    stu = create_user(tmp_db, "melisa", hash_password("pw123456"), email="melisa@std.medipol.edu.tr")
    assign_supervisor(tmp_db, stu.id, prof.id)
    c = TestClient(create_app(tmp_db))
    tok = c.post("/api/v1/auth/login", json={"username": "melisa", "password": "pw123456"}).json()["token"]
    r = c.get("/api/v1/supervision/my-supervisor", headers={"Authorization": f"Bearer {tok}"}).json()
    assert r["professor_name"] == "kaya"
