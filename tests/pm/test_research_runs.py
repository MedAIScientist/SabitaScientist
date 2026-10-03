"""AutoResearchClaw runs: who may start, who decides which gate, what gets imported."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gazzali import research_claw as arc
from gazzali.api.app import create_app
from gazzali.auth import hash_password
from gazzali.crud import labs as labs_crud
from gazzali.crud import projects as projects_crud
from gazzali.crud.experiment_metrics import list_metrics
from gazzali.crud.experiments import create_experiment
from gazzali.crud.irb import create_irb
from gazzali.crud.users import create_user


class FakeWorker:
    """Stands in for the ARC worker; records calls, returns scripted state."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []
        self.state: dict = {"state": "running", "stage": 3, "stage_name": "SEARCH_STRATEGY"}
        self.down = False
        self.registry = {"values": [[0.912, "logreg/recall mean"], [0.034, "logreg/recall std"]]}
        self.lessons = [
            {"stage_name": "experiment_design", "category": "design", "severity": "warning",
             "description": "240-cell factorial exceeded the time budget", "timestamp": "2026-10-01T00:00:00+00:00"},
            {"stage_name": "literature_screen", "category": "literature", "severity": "error",
             "description": "All models failed. Last error: HTTP Error 413", "timestamp": "2026-10-01T00:00:00+00:00"},
        ]

    def __call__(self, method: str, path: str, json_body: dict | None = None, timeout: float = 15):
        if self.down:
            raise arc.WorkerError("AutoResearchClaw worker unreachable: refused")
        self.calls.append((method, path, json_body))
        if path == "/jobs":
            return {"state": "running"}
        if path.endswith("/registry"):
            return self.registry
        if path.endswith("/lessons"):
            return self.lessons
        if "/file?" in path:
            return {"path": "stage-09/exp_plan.yaml", "content": "conditions: 60"}
        if path.endswith(("/response", "/cancel")):
            return {"status": "ok"}
        return self.state


@pytest.fixture
def worker(monkeypatch) -> FakeWorker:
    fake = FakeWorker()
    monkeypatch.setattr(arc, "_call", fake)
    return fake


def _login(client: TestClient, name: str) -> dict:
    tok = client.post("/api/v1/auth/login", json={"username": name, "password": "pw123456"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def world(tmp_db: Path) -> dict:
    users = {n: create_user(tmp_db, n, hash_password("pw123456"), email=f"{n}@medipol.edu.tr")
             for n in ("pi", "student", "editor", "viewer", "outsider")}
    lab = labs_crud.create_lab(tmp_db, "Retina Lab", pi_id=users["pi"].id)
    project = projects_crud.create_project(tmp_db, "DR screening", users["student"].id, lab_id=lab.id)
    projects_crud.add_member(tmp_db, project.id, users["editor"].id, "editor")
    projects_crud.add_member(tmp_db, project.id, users["viewer"].id, "viewer")
    exp = create_experiment(tmp_db, project.id, "Class weighting", users["student"].id,
                            hypothesis="Class weighting raises minority-class recall of logistic regression")
    client = TestClient(create_app(tmp_db))
    return {"db": tmp_db, "client": client, "lab": lab, "project": project, "exp": exp,
            "h": {n: _login(client, n) for n in users}, "users": users}


def _runs_url(w: dict) -> str:
    return f"/api/v1/projects/{w['project'].id}/experiments/{w['exp'].id}/research-runs"


def _start(w: dict, who: str = "student", **body) -> object:
    return w["client"].post(_runs_url(w), json=body, headers=w["h"][who])


def test_owner_starts_a_copilot_run_seeded_with_lab_lessons(world, worker) -> None:
    from gazzali.db import get_db

    with get_db(world["db"]) as conn:
        conn.execute(
            "INSERT INTO research_lessons (id, lab_id, run_id, category, severity, lesson_json, created_at) VALUES ('l1', ?, NULL, 'design', 0.6, ?, ?)",
            (world["lab"].id, json.dumps({"description": "keep designs small"}), datetime.now(UTC).isoformat()),
        )
    r = _start(world)
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["mode"] == "co-pilot"
    assert run["topic"].startswith("Class weighting raises")
    method, path, body = worker.calls[0]
    assert (method, path) == ("POST", "/jobs")
    assert body["job_id"] == run["id"]
    assert body["lessons"] == [{"description": "keep designs small"}]


def test_viewers_and_outsiders_cannot_start(world, worker) -> None:
    assert _start(world, "viewer").status_code == 403
    assert _start(world, "outsider").status_code == 404
    assert worker.calls == []


def test_patient_data_needs_an_active_irb_of_the_project(world, worker) -> None:
    db, student = world["db"], world["users"]["student"]
    assert _start(world, dataset="dr/fundus").status_code == 400
    draft = create_irb(db, world["project"].id, "Medipol", "E-1", "DR", student.id)
    assert _start(world, dataset="dr/fundus", irb_id=draft.id).status_code == 400
    expired = create_irb(db, world["project"].id, "Medipol", "E-2", "DR", student.id,
                         status="approved", expiry_date=(datetime.now(UTC) - timedelta(days=1)).date().isoformat())
    assert _start(world, dataset="dr/fundus", irb_id=expired.id).status_code == 400
    ok = create_irb(db, world["project"].id, "Medipol", "E-3", "DR", student.id, status="approved")
    r = _start(world, dataset="dr/fundus", irb_id=ok.id)
    assert r.status_code == 201
    assert r.json()["irb_id"] == ok.id
    assert worker.calls[-1][2]["dataset"] == "dr/fundus"


def test_worker_down_fails_the_run_visibly(world, worker) -> None:
    worker.down = True
    r = _start(world)
    assert r.status_code == 503
    worker.down = False
    worker.state = {"state": "failed"}
    runs = world["client"].get(_runs_url(world), headers=world["h"]["student"]).json()
    assert runs[0]["status"] == "failed"
    assert "unreachable" in runs[0]["error"]


def test_pre_experiment_gate_is_decided_by_the_project_team(world, worker) -> None:
    run = _start(world).json()
    worker.state = {"state": "waiting", "stage": 9, "stage_name": "EXPERIMENT_DESIGN", "waiting": {"stage": 9}}
    c, h = world["client"], world["h"]
    assert [g["id"] for g in c.get("/api/v1/research-runs/gates", headers=h["editor"]).json()] == [run["id"]]
    assert c.post(f"/api/v1/research-runs/{run['id']}/respond", json={"action": "approve"}, headers=h["viewer"]).status_code == 403
    r = c.post(f"/api/v1/research-runs/{run['id']}/respond",
               json={"action": "approve", "guidance": "use 60 cells, not 240"}, headers=h["editor"])
    assert r.status_code == 200
    assert worker.calls[-1][1].endswith("/response")
    assert worker.calls[-1][2]["guidance"] == "use 60 cells, not 240"


def test_post_experiment_gate_needs_the_lab_pi(world, worker) -> None:
    run = _start(world).json()
    worker.state = {"state": "waiting", "stage": 14, "stage_name": "RESULT_ANALYSIS", "waiting": {"stage": 14}}
    c, h = world["client"], world["h"]
    assert c.get("/api/v1/research-runs/gates", headers=h["student"]).json() == []
    r = c.post(f"/api/v1/research-runs/{run['id']}/respond", json={"action": "approve"}, headers=h["student"])
    assert r.status_code == 403
    assert "PI" in r.json()["detail"]
    assert [g["id"] for g in c.get("/api/v1/research-runs/gates", headers=h["pi"]).json()] == [run["id"]]
    assert c.post(f"/api/v1/research-runs/{run['id']}/respond", json={"action": "approve"}, headers=h["pi"]).status_code == 200
    assert c.post(f"/api/v1/research-runs/{run['id']}/respond", json={"action": "approve"}, headers=h["outsider"]).status_code == 404


def test_finished_run_imports_registry_and_research_lessons_once(world, worker) -> None:
    run = _start(world).json()
    worker.state = {"state": "done", "stage": 23, "stage_name": "CITATION_VERIFY"}
    c, h = world["client"], world["h"]
    assert c.get(_runs_url(world), headers=h["student"]).json()[0]["status"] == "done"
    c.get(_runs_url(world), headers=h["student"])  # a second read must not import again
    values = sorted(m.value for m in list_metrics(world["db"], world["exp"].id))
    assert values == [0.034, 0.912]
    assert c.get(f"/api/v1/labs/{world['lab'].id}/research-lessons", headers=h["outsider"]).status_code == 403
    lessons = c.get(f"/api/v1/labs/{world['lab'].id}/research-lessons", headers=h["pi"]).json()
    assert [entry["category"] for entry in lessons] == ["design"]  # the HTTP 413 one is infrastructure noise
    assert lessons[0]["run_id"] == run["id"]
    assert c.delete(f"/api/v1/labs/{world['lab'].id}/research-lessons/{lessons[0]['id']}", headers=h["student"]).status_code == 403
    assert c.delete(f"/api/v1/labs/{world['lab'].id}/research-lessons/{lessons[0]['id']}", headers=h["pi"]).status_code == 204


def test_lesson_weight_halves_every_thirty_days() -> None:
    now = datetime(2026, 10, 3, tzinfo=UTC)
    assert arc.lesson_weight(0.8, now, now) == pytest.approx(0.8)
    assert arc.lesson_weight(0.8, now - timedelta(days=30), now) == pytest.approx(0.4)
    assert arc.lesson_weight(0.8, now - timedelta(days=60), now) == pytest.approx(0.2)


def test_gate_artifacts_are_readable_by_the_team_only(world, worker) -> None:
    run = _start(world).json()
    c, h = world["client"], world["h"]
    url = f"/api/v1/research-runs/{run['id']}/file?path=stage-09/exp_plan.yaml"
    assert c.get(url, headers=h["viewer"]).json()["content"] == "conditions: 60"
    assert worker.calls[-1][1] == f"/jobs/{run['id']}/file?path=stage-09%2Fexp_plan.yaml"
    assert c.get(url, headers=h["outsider"]).status_code == 404
