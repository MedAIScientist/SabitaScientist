"""Paper pipeline: context pack, outline, integrity, review points."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gazzali.api.app import create_app
from gazzali.auth import hash_password
from gazzali.crud.users import create_user
import gazzali.api.deps as deps


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db = tmp_path / "pm.db"
    monkeypatch.setenv("EVOSCIENTIST_PM_DB", str(db))
    monkeypatch.setenv("GAZZALI_PM_DB", str(db))
    create_app(db)
    admin = create_user(db, "admin", hash_password("secret123"), is_admin=True, role="admin")
    app = create_app(db)
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"username": "admin", "password": "secret123"})
    c.token = r.json()["token"]
    c.admin_id = admin.id
    c.db = db
    return c


def _h(c) -> dict:
    return {"Authorization": f"Bearer {c.token}"}


def _make_project_and_exp(c) -> tuple[str, str]:
    r = c.post("/api/v1/projects", json={"name": "Paper Project", "description": "Study X"}, headers=_h(c))
    project_id = r.json()["id"]
    r = c.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Exp A", "hypothesis": "H1", "protocol": "P1"},
        headers=_h(c),
    )
    exp_id = r.json()["id"]
    return project_id, exp_id


def test_context_pack_includes_project_and_experiments(client: TestClient) -> None:
    project_id, exp_id = _make_project_and_exp(client)
    r = client.post(
        "/api/v1/publications",
        json={"title": "My Paper", "project_id": project_id},
        headers=_h(client),
    )
    # publications create path
    if r.status_code >= 400:
        r = client.post(
            "/api/v1/publications/",
            json={"title": "My Paper", "project_id": project_id},
            headers=_h(client),
        )
    assert r.status_code in (200, 201), r.text
    pub_id = r.json()["id"]

    r = client.post(
        f"/api/v1/publications/{pub_id}/context",
        json={"snapshot": True, "label": "first pack"},
        headers=_h(client),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    counts = data["summary"]["counts"]
    assert counts["project"] == 1
    assert counts["experiments"] == 1
    assert data["snapshot"] is not None
    assert any(eid.startswith("exp:") for eid in data["evidence_ids"])

    r = client.get(f"/api/v1/publications/{pub_id}/context", headers=_h(client))
    assert r.status_code == 200
    assert len(r.json()["snapshots"]) >= 1


def test_outline_generate_binds_evidence(client: TestClient) -> None:
    project_id, exp_id = _make_project_and_exp(client)
    r = client.post("/api/v1/publications", json={"title": "Outline Paper", "project_id": project_id}, headers=_h(client))
    if r.status_code >= 400:
        r = client.post("/api/v1/publications/", json={"title": "Outline Paper", "project_id": project_id}, headers=_h(client))
    pub_id = r.json()["id"]

    r = client.post(f"/api/v1/publications/{pub_id}/outline/generate", headers=_h(client))
    assert r.status_code == 200, r.text
    claims = r.json()["claims"]
    assert any(c["section"] == "results" for c in claims)
    assert any(c["evidence_ids"] for c in claims)

    r = client.get(f"/api/v1/publications/{pub_id}/outline", headers=_h(client))
    assert r.status_code == 200
    assert len(r.json()["claims"]) >= 4


def test_integrity_fails_without_metrics(client: TestClient) -> None:
    project_id, exp_id = _make_project_and_exp(client)
    r = client.post("/api/v1/publications", json={"title": "Integrity Paper", "project_id": project_id}, headers=_h(client))
    if r.status_code >= 400:
        r = client.post("/api/v1/publications/", json={"title": "Integrity Paper", "project_id": project_id}, headers=_h(client))
    pub_id = r.json()["id"]

    r = client.post(f"/api/v1/publications/{pub_id}/integrity", headers=_h(client))
    assert r.status_code == 200, r.text
    data = r.json()
    by_id = {c["id"]: c for c in data["checks"]}
    assert by_id["numbers"]["passed"] is False
    assert data["passed"] is False


def test_review_points_and_pipeline(client: TestClient) -> None:
    r = client.post("/api/v1/publications", json={"title": "Review Paper"}, headers=_h(client))
    if r.status_code >= 400:
        r = client.post("/api/v1/publications/", json={"title": "Review Paper"}, headers=_h(client))
    pub_id = r.json()["id"]

    r = client.post(
        f"/api/v1/publications/{pub_id}/review-points",
        json={"comment": "Unclear methods", "section": "methods", "action": "expand protocol"},
        headers=_h(client),
    )
    assert r.status_code == 201, r.text

    r = client.get(f"/api/v1/publications/{pub_id}/review-points", headers=_h(client))
    assert len(r.json()["points"]) == 1

    r = client.get(f"/api/v1/publications/{pub_id}/stages", headers=_h(client))
    assert r.status_code == 200
    stages = r.json()["stages"]
    assert stages["setup"] is True
    assert "outline" in stages

    r = client.post(f"/api/v1/publications/{pub_id}/submit-pack", headers=_h(client))
    assert r.status_code == 200
    assert r.json()["open_review_points"] == 1


def test_context_pack_handles_phases_and_wiki_columns(client: TestClient) -> None:
    """Regression: project_phases has no description/status; wiki uses content not body."""
    project_id, _exp_id = _make_project_and_exp(client)
    r = client.post(
        f"/api/v1/projects/{project_id}/phases",
        json={"name": "Phase 1", "color": "#6366f1", "position": 0, "target_date": "2026-12-01"},
        headers=_h(client),
    )
    assert r.status_code in (200, 201), r.text

    r = client.post("/api/v1/publications", json={"title": "Phases Paper", "project_id": project_id}, headers=_h(client))
    if r.status_code >= 400:
        r = client.post("/api/v1/publications/", json={"title": "Phases Paper", "project_id": project_id}, headers=_h(client))
    pub_id = r.json()["id"]

    r = client.post(f"/api/v1/publications/{pub_id}/context", json={}, headers=_h(client))
    assert r.status_code == 200, r.text
    counts = r.json()["summary"]["counts"]
    assert counts["phases"] == 1

    # Context text must include the phase without KeyError/IndexError
    assert any("Phase 1" in x["label"] for x in r.json()["sources"]["phases"])


def test_build_paper_context_full_corpus(tmp_path: Path) -> None:
    """Unit test: every corpus source must map to real columns (regression for body/content)."""
    from gazzali import paper_context
    from gazzali.db import create_schema, get_db
    from gazzali.crud.users import create_user as cu
    from gazzali.auth import hash_password as hp
    from datetime import UTC, datetime

    db = tmp_path / "ctx.db"
    create_schema(db)
    now = datetime.now(UTC).isoformat()
    with get_db(db) as c:
        uid = "u1"
        c.execute(
            "INSERT INTO users (id, username, password_hash, is_admin, role, created_at) VALUES (?,?,?,?,?,?)",
            (uid, "alice", hp("secret123"), 1, "admin", now),
        )
        c.execute("INSERT INTO labs (id, name, pi_id, created_at, updated_at) VALUES (?,?,?,?,?)", ("l1", "Lab", uid, now, now))
        c.execute(
            "INSERT INTO projects (id, name, description, lab_id, created_by, created_at) VALUES (?,?,?,?,?,?)",
            ("p1", "Proj", "Desc", "l1", uid, now),
        )
        c.execute(
            "INSERT INTO project_phases (id, project_id, name, color, position, target_date, created_by, created_at) VALUES (?,?,?,?,?,?,?,?)",
            ("ph1", "p1", "Phase 1", "#fff", 0, "2026-12-01", uid, now),
        )
        c.execute(
            "INSERT INTO lab_wiki_pages (id, lab_id, title, slug, content, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            ("w1", "l1", "Methods note", "methods", "Use protocol X", uid, now, now),
        )
        c.execute(
            "INSERT INTO grants (id, project_id, title, funder, status, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            ("g1", "p1", "Grant A", "TÜBİTAK", "awarded", uid, now, now),
        )
        c.execute(
            "INSERT INTO irb_approvals (id, project_id, institution, protocol_number, title, status, approval_date, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("i1", "p1", "Medipol", "IRB-1", "Ethics", "approved", "2026-01-01", uid, now, now),
        )
        c.execute(
            "INSERT INTO experiments (id, project_id, name, status, tags, created_by, created_at, updated_at, hypothesis, protocol) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("e1", "p1", "Exp A", "completed", "[]", uid, now, now, "H", "P"),
        )
        c.execute(
            "INSERT INTO experiment_metrics (id, experiment_id, name, value, unit, created_at) VALUES (?,?,?,?,?,?)",
            ("m1", "e1", "accuracy", "0.92", "", now),
        )

    pack = paper_context.build_paper_context(db, "p1", None)
    counts = pack["summary"]["counts"]
    assert counts["phases"] == 1
    assert counts["wiki"] == 1
    assert counts["funding"] == 1
    assert counts["ethics"] == 1
    assert counts["experiments"] == 1
    assert "Phase 1" in pack["text"]
    assert "Use protocol X" in pack["text"]
    assert "metric:m1" in pack["evidence_ids"]
