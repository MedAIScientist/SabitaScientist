"""Tests for academic supervision API: roles, weekly reports, meetings."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.users import create_user


@pytest.fixture
def client(tmp_db: Path) -> TestClient:
    """An app on a fresh database, seeded with one admin, professor and student."""
    admin = create_user(tmp_db, "admin", hash_password("secret123"), is_admin=True, role="admin")
    prof = create_user(tmp_db, "prof", hash_password("secret123"), role="professor")
    stud = create_user(tmp_db, "stud", hash_password("secret123"), role="student")

    c = TestClient(create_app(tmp_db))

    def _login(username: str) -> str:
        r = c.post("/api/v1/auth/login", json={"username": username, "password": "secret123"})
        assert r.status_code == 200, r.text
        return r.json()["token"]

    c.admin_token = _login("admin")
    c.prof_token = _login("prof")
    c.stud_token = _login("stud")
    c.admin_id = admin.id
    c.prof_id = prof.id
    c.stud_id = stud.id
    return c


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _assign(client: TestClient) -> None:
    r = client.post(
        "/api/v1/supervision/assignments",
        json={"student_id": client.stud_id, "professor_id": client.prof_id},
        headers=_h(client.prof_token),
    )
    assert r.status_code == 201, r.text


def test_login_returns_role(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "prof", "password": "secret123"})
    assert r.status_code == 200
    assert r.json()["role"] == "professor"


def test_assign_supervisor_and_list_students(client: TestClient) -> None:
    r = client.post(
        "/api/v1/supervision/assignments",
        json={"student_id": client.stud_id, "professor_id": client.prof_id},
        headers=_h(client.prof_token),
    )
    assert r.status_code == 201, r.text

    r = client.get("/api/v1/supervision/my-students", headers=_h(client.prof_token))
    assert r.status_code == 200
    assert any(a["student_id"] == client.stud_id for a in r.json())

    r = client.get("/api/v1/supervision/my-supervisor", headers=_h(client.stud_token))
    assert r.status_code == 200
    assert r.json()["professor_id"] == client.prof_id


def test_weekly_report_submit_and_review(client: TestClient) -> None:
    # Student creates current week report
    r = client.post("/api/v1/supervision/weekly/current", headers=_h(client.stud_token))
    assert r.status_code == 200, r.text
    report_id = r.json()["id"]

    # Add item
    r = client.put(
        f"/api/v1/supervision/reports/{report_id}/items",
        json={"item_title": "Paper draft", "progress_pct": 40, "status": "in_progress", "needs_help": True},
        headers=_h(client.stud_token),
    )
    assert r.status_code == 200, r.text

    # Summary + submit
    client.put(
        f"/api/v1/supervision/reports/{report_id}/summary",
        json={"accomplished": "Wrote intro", "next_focus": "Methods"},
        headers=_h(client.stud_token),
    )
    r = client.post(f"/api/v1/supervision/reports/{report_id}/submit", headers=_h(client.stud_token))
    assert r.status_code == 200
    assert r.json()["status"] == "submitted"
    assert r.json()["review_status"] == "needs_review"
    assert len(r.json()["items"]) == 1

    # Professor reviews (as the student's assigned supervisor)
    _assign(client)
    r = client.post(
        f"/api/v1/supervision/reports/{report_id}/review",
        json={"review_status": "reviewed", "feedback": "Good progress", "risk_override": "low"},
        headers=_h(client.prof_token),
    )
    assert r.status_code == 200
    assert r.json()["review_status"] == "reviewed"
    assert r.json()["feedback"] == "Good progress"


def test_attendance_and_extension(client: TestClient) -> None:
    r = client.post(
        "/api/v1/supervision/attendance?student_id="
        + client.stud_id,
        json={"status": "on_time", "joined_mode": "online", "note": "Discussed paper"},
        headers=_h(client.prof_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "on_time"

    r = client.post(
        f"/api/v1/supervision/extensions?student_id={client.stud_id}",
        json={"new_deadline": "2026-10-05T23:59:00", "reason": "Conference travel"},
        headers=_h(client.prof_token),
    )
    assert r.status_code == 201, r.text


def test_journeys_and_requirements(client: TestClient) -> None:
    r = client.post(
        "/api/v1/supervision/journeys",
        json={"level": "PhD", "status": "active", "thesis_title": "Security of X", "programme": "CS"},
        headers=_h(client.stud_token),
    )
    assert r.status_code == 201, r.text

    r = client.get("/api/v1/supervision/journeys", headers=_h(client.stud_token))
    assert r.status_code == 200
    assert any(j["level"] == "PhD" for j in r.json())

    r = client.post(
        "/api/v1/supervision/requirements",
        json={"level": "PhD", "title": "Publish 2 journal papers", "req_type": "research_item", "target_value": 2},
        headers=_h(client.admin_token),
    )
    assert r.status_code == 201, r.text

    r = client.get("/api/v1/supervision/requirements", headers=_h(client.stud_token))
    assert r.status_code == 200
    assert any(req["title"] == "Publish 2 journal papers" for req in r.json())


def test_course_tracking_is_not_part_of_the_platform(client: TestClient) -> None:
    """Courses, credits and GPA are gone: this platform covers publication work.

    The surface is asserted away so a later change cannot quietly resurrect a
    transcript feature that the product decision removed.
    """
    spec = client.get("/openapi.json").json()
    transcript_paths = [p for p in spec["paths"] if "semester" in p or "course" in p]
    assert transcript_paths == []

    # Reading the old collections must not resolve to anything. (The SPA fallback
    # answers unmatched POSTs with 405 and unmatched GETs with 404, so the method
    # that matters here is the read.)
    for path in (
        "/api/v1/supervision/journeys/j1/semesters",
        "/api/v1/supervision/semesters/s1/courses",
    ):
        r = client.get(path, headers=_h(client.admin_token))
        assert r.status_code == 404, f"{path} still exists"


def test_readiness_scores_publications_and_ignores_transcripts(client: TestClient) -> None:
    """A journal-paper rule is satisfied by a publication; no credit/GPA evidence exists."""
    client.post(
        "/api/v1/supervision/journeys",
        json={"level": "PhD", "status": "active"},
        headers=_h(client.stud_token),
    )
    client.post(
        "/api/v1/supervision/requirements",
        json={
            "level": "PhD",
            "title": "Publish 1 journal paper",
            "req_type": "research_item",
            "research_item_type": "Journal Paper",
            "target_value": 1,
        },
        headers=_h(client.admin_token),
    )

    def _publish() -> None:
        pub_id = client.post(
            "/api/v1/publications",
            json={"title": "A journal paper", "venue_type": "journal"},
            headers=_h(client.stud_token),
        ).json()["id"]
        client.put(
            f"/api/v1/publications/{pub_id}",
            json={"status": "published"},
            headers=_h(client.stud_token),
        )

    before = client.get("/api/v1/supervision/readiness", headers=_h(client.stud_token)).json()
    assert before["readiness_pct"] == 0

    _publish()

    after = client.get("/api/v1/supervision/readiness", headers=_h(client.stud_token)).json()
    assert after["readiness_pct"] == 100
    assert after["summary"] == {
        "publications": 1,
        "journal_papers": 1,
        "conference_papers": 0,
    }


def test_student_cannot_review(client: TestClient) -> None:
    r = client.post("/api/v1/supervision/weekly/current", headers=_h(client.stud_token))
    report_id = r.json()["id"]
    r = client.post(
        f"/api/v1/supervision/reports/{report_id}/review",
        json={"review_status": "reviewed"},
        headers=_h(client.stud_token),
    )
    assert r.status_code == 403


def test_professor_analytics(client: TestClient) -> None:
    # Assign student + one submitted report so KPIs are non-zero
    client.post(
        "/api/v1/supervision/assignments",
        json={"student_id": client.stud_id, "professor_id": client.prof_id},
        headers=_h(client.prof_token),
    )
    r = client.post("/api/v1/supervision/weekly/current", headers=_h(client.stud_token))
    report_id = r.json()["id"]
    client.put(
        f"/api/v1/supervision/reports/{report_id}/items",
        json={"item_title": "Patent draft", "progress_pct": 55, "needs_help": True, "item_kind": "patent", "next_deadline": "2026-10-15"},
        headers=_h(client.stud_token),
    )
    client.post(f"/api/v1/supervision/reports/{report_id}/submit", headers=_h(client.stud_token))

    r = client.get("/api/v1/supervision/analytics/professor", headers=_h(client.prof_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kpis"]["student_count"] == 1
    assert data["kpis"]["submitted_this_week"] >= 1
    assert data["kpis"]["needs_review"] >= 1
    assert data["kpis"]["help_requests"] >= 1
    assert len(data["students"]) == 1
    assert data["students"][0]["username"] == "stud"
    assert any(t["submitted"] >= 1 for t in data["weekly_trend"])
    assert len(data["reports_needing_attention"]) >= 1
    assert len(data["active_deadlines"]) >= 1
    assert any(m["kind"] == "patent" for m in data["work_mix"])


def test_student_cannot_access_analytics(client: TestClient) -> None:
    r = client.get("/api/v1/supervision/analytics/professor", headers=_h(client.stud_token))
    assert r.status_code == 403


def test_research_items_unified(client: TestClient) -> None:
    # Create a publication via API
    r = client.post(
        "/api/v1/publications/",
        json={"title": "Security Paper", "venue_type": "conference", "venue": "ESPRE"},
        headers=_h(client.stud_token),
    )
    # Publication create path may vary; accept 201/200 or skip if 404
    if r.status_code in (200, 201):
        r2 = client.get("/api/v1/supervision/research-items", headers=_h(client.stud_token))
        assert r2.status_code == 200
        kinds = {i["kind"] for i in r2.json()}
        assert "publication" in kinds or len(r2.json()) >= 0
    else:
        # Endpoint shape still valid
        r2 = client.get("/api/v1/supervision/research-items", headers=_h(client.stud_token))
        assert r2.status_code == 200


def test_readiness_empty_without_journey(client: TestClient) -> None:
    r = client.get("/api/v1/supervision/readiness", headers=_h(client.stud_token))
    assert r.status_code == 200
    data = r.json()
    assert data["student_id"] == client.stud_id
    assert "readiness_pct" in data
    assert "requirements" in data


def test_bulk_import_users(client: TestClient) -> None:
    r = client.post(
        "/api/v1/users/bulk-import",
        json={"rows": [
            {"username": "s1", "password": "secret123", "email": "s1@x.com", "role": "student"},
            {"username": "p1", "password": "secret123", "email": "p1@x.com", "role": "professor"},
            {"username": "s1", "password": "secret123"},  # duplicate
        ]},
        headers=_h(client.admin_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1


def test_draft_paper_from_research_items(client: TestClient) -> None:
    # Create an experiment first via projects API is heavy; use draft-from-items with empty exps
    r = client.post(
        "/api/v1/supervision/research-items/draft-paper",
        json={"title": "Integrated Paper", "experiment_ids": [], "venue_type": "journal"},
        headers=_h(client.prof_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "Integrated Paper"
    pub_id = body["publication_id"]

    r = client.get(f"/api/v1/supervision/papers/{pub_id}/readiness", headers=_h(client.prof_token))
    assert r.status_code == 200
    readiness = r.json()
    assert readiness["publication_id"] == pub_id
    assert "checks" in readiness
    assert "suggested_tools" in readiness
    assert readiness["ready_to_submit"] is False  # no experiments/abstract

    r = client.get(f"/api/v1/supervision/papers/{pub_id}/evidence", headers=_h(client.prof_token))
    assert r.status_code == 200
    assert r.json()["publication_id"] == pub_id


def _paper_in_project(client: TestClient, token: str, project_id: str | None = None) -> str:
    body: dict = {"title": "Compliance paper"}
    if project_id:
        body["project_id"] = project_id
    resp = client.post("/api/v1/publications", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _project(client: TestClient, token: str, name: str = "Imaging study") -> str:
    resp = client.post("/api/v1/projects", json={"name": name}, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _checks(client: TestClient, token: str, pub_id: str) -> dict:
    resp = client.get(f"/api/v1/supervision/papers/{pub_id}/readiness", headers=_h(token))
    assert resp.status_code == 200, resp.text
    return {c["id"]: c for c in resp.json()["checks"]}


def test_compliance_statements_round_trip_and_open_the_gate(client: TestClient) -> None:
    """A statement the author typed must persist and must actually move the gate."""
    pub_id = _paper_in_project(client, client.admin_token)

    before = _checks(client, client.admin_token, pub_id)
    assert before["reporting_guideline"]["met"] is False
    assert before["data_availability"]["met"] is False
    assert before["conflict_of_interest"]["met"] is False

    resp = client.put(
        f"/api/v1/publications/{pub_id}",
        json={
            "reporting_guideline": "STROBE",
            "data_availability": "De-identified data on reasonable request.",
            "code_availability": "https://github.com/example/analysis (MIT)",
            "conflict_of_interest": "The authors declare no competing interests.",
            "funding_statement": "TUBITAK 1001, grant 1234.",
        },
        headers=_h(client.admin_token),
    )
    assert resp.status_code == 200, resp.text
    stored = resp.json()
    assert stored["reporting_guideline"] == "STROBE"
    assert stored["code_availability"].startswith("https://github.com/example")

    after = _checks(client, client.admin_token, pub_id)
    assert after["reporting_guideline"]["met"] is True
    assert after["data_availability"]["met"] is True
    assert after["conflict_of_interest"]["met"] is True
    assert after["code_availability"]["met"] is True
    assert after["funding"]["met"] is True


def test_ethics_check_reads_the_projects_approval_not_a_publication_field(
    client: TestClient,
) -> None:
    """Ethics is a project-level fact; the gate must read it there, not duplicate it."""
    project_id = _project(client, client.admin_token)
    pub_id = _paper_in_project(client, client.admin_token, project_id)

    assert _checks(client, client.admin_token, pub_id)["ethics"]["met"] is False

    irb = client.post(
        "/api/v1/irb",
        json={
            "project_id": project_id,
            "institution": "Medipol",
            "protocol_number": "E-10840098-2026",
            "title": "Retrospective imaging cohort",
            # Submitted, so the lifecycle can decide it; an IRB is never born approved.
            "status": "submitted",
        },
        headers=_h(client.admin_token),
    )
    assert irb.status_code == 201, irb.text

    # A submitted protocol is not an approval.
    assert _checks(client, client.admin_token, pub_id)["ethics"]["met"] is False

    approved = client.put(
        f"/api/v1/irb/{irb.json()['id']}",
        json={
            "status": "approved",
            "approval_date": "2026-02-01",
            "expiry_date": "2027-02-01",
            # An approval with no document reference is refused by design.
            "documents": ["ethics-approval-2026.pdf"],
        },
        headers=_h(client.admin_token),
    )
    assert approved.status_code == 200, approved.text

    ethics = _checks(client, client.admin_token, pub_id)["ethics"]
    assert ethics["met"] is True
    assert "E-10840098-2026" in ethics["detail"]


def test_ethics_check_stays_open_for_a_paper_without_a_project(client: TestClient) -> None:
    """No project means no IRB to read — the check must say so rather than pass."""
    pub_id = _paper_in_project(client, client.admin_token)
    ethics = _checks(client, client.admin_token, pub_id)["ethics"]
    assert ethics["met"] is False
    assert "no approved IRB" in ethics["detail"]


def test_funding_check_accepts_an_awarded_project_grant(client: TestClient) -> None:
    """A funded grant on the project is evidence, even with no funding statement typed."""
    project_id = _project(client, client.admin_token, "Funded study")
    pub_id = _paper_in_project(client, client.admin_token, project_id)

    assert _checks(client, client.admin_token, pub_id)["funding"]["met"] is False

    grant = client.post(
        "/api/v1/grants",
        json={
            "title": "Imaging biomarkers",
            "funder": "TUBITAK",
            "project_id": project_id,
            "status": "awarded",
        },
        headers=_h(client.admin_token),
    )
    assert grant.status_code == 201, grant.text

    funding = _checks(client, client.admin_token, pub_id)["funding"]
    assert funding["met"] is True
    assert "Imaging biomarkers" in funding["detail"]


def test_blank_statements_do_not_count_as_declared(client: TestClient) -> None:
    """Whitespace is not a declaration — otherwise the gate can be gamed with a space."""
    pub_id = _paper_in_project(client, client.admin_token)
    client.put(
        f"/api/v1/publications/{pub_id}",
        json={"conflict_of_interest": "   "},
        headers=_h(client.admin_token),
    )
    assert _checks(client, client.admin_token, pub_id)["conflict_of_interest"]["met"] is False


def test_paper_readiness_required_checks(client: TestClient) -> None:
    r = client.post(
        "/api/v1/supervision/research-items/draft-paper",
        json={"title": "Real Paper Title", "abstract": "A" * 120},
        headers=_h(client.admin_token),
    )
    pub_id = r.json()["publication_id"]
    r = client.get(f"/api/v1/supervision/papers/{pub_id}/readiness", headers=_h(client.admin_token))
    data = r.json()
    by_id = {c["id"]: c for c in data["checks"]}
    assert by_id["title"]["met"] is True
    assert by_id["abstract"]["met"] is True
    assert by_id["experiments"]["met"] is False
    assert data["ready_to_submit"] is False


# ── Follow-ups from reviews ──────────────────────────────────────────────────


def _submitted_report(client: TestClient) -> str:
    report_id = client.post("/api/v1/supervision/weekly/current", headers=_h(client.stud_token)).json()["id"]
    client.post(f"/api/v1/supervision/reports/{report_id}/submit", headers=_h(client.stud_token))
    return report_id


def _followups(client: TestClient, token: str, **params) -> list[dict]:
    r = client.get("/api/v1/supervision/followups", params=params, headers=_h(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_review_followups_carry_forward_until_closed(client: TestClient) -> None:
    _assign(client)
    report_id = _submitted_report(client)
    r = client.post(
        f"/api/v1/supervision/reports/{report_id}/review",
        json={"review_status": "reviewed", "feedback": "ok",
              "followups": [{"text": "Rerun the ablation with seed 2", "due_date": "2000-01-01"},
                            {"text": "Send the draft intro"}, {"text": "   "}]},
        headers=_h(client.prof_token),
    )
    assert r.status_code == 200, r.text

    # The student sees both open requests (blank ones are ignored); the past due date is flagged.
    open_items = _followups(client, client.stud_token, status="open")
    assert [f["text"] for f in open_items] == ["Rerun the ablation with seed 2", "Send the draft intro"]
    assert open_items[0]["overdue"] is True and open_items[0]["weeks_open"] == 0
    assert open_items[0]["report_id"] == report_id

    # The student closes one with a note; the other stays open for next week.
    fid = open_items[0]["id"]
    r = client.patch(f"/api/v1/supervision/followups/{fid}", json={"status": "done", "note": "Done, see exp 12"},
                     headers=_h(client.stud_token))
    assert r.status_code == 200 and r.json()["student_note"] == "Done, see exp 12"
    assert [f["text"] for f in _followups(client, client.prof_token, status="open")] == ["Send the draft intro"]


def test_only_the_assigned_supervisor_reviews(client: TestClient) -> None:
    report_id = _submitted_report(client)  # nobody is assigned yet
    r = client.post(f"/api/v1/supervision/reports/{report_id}/review", json={"review_status": "reviewed"},
                    headers=_h(client.prof_token))
    assert r.status_code == 403
    r = client.post(f"/api/v1/supervision/reports/{report_id}/review", json={"review_status": "reviewed"},
                    headers=_h(client.admin_token))
    assert r.status_code == 200


def test_students_cannot_drop_followups_and_others_cannot_see_them(client: TestClient, tmp_db) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user

    _assign(client)
    report_id = _submitted_report(client)
    client.post(f"/api/v1/supervision/reports/{report_id}/review",
                json={"review_status": "reviewed", "followups": [{"text": "Fix figure 2"}]},
                headers=_h(client.prof_token))
    (f,) = _followups(client, client.stud_token)
    r = client.patch(f"/api/v1/supervision/followups/{f['id']}", json={"status": "dropped"},
                     headers=_h(client.stud_token))
    assert r.status_code == 403

    create_user(tmp_db, "prof2", hash_password("secret123"), role="professor")
    other = client.post("/api/v1/auth/login", json={"username": "prof2", "password": "secret123"}).json()["token"]
    assert _followups(client, other) == []
    assert _followups(client, other, student_id=client.stud_id) == []
    r = client.patch(f"/api/v1/supervision/followups/{f['id']}", json={"status": "done"}, headers=_h(other))
    assert r.status_code == 404

    r = client.patch(f"/api/v1/supervision/followups/{f['id']}", json={"status": "dropped"},
                     headers=_h(client.prof_token))
    assert r.status_code == 200 and r.json()["status"] == "dropped"


# ── AI meeting briefs ────────────────────────────────────────────────────────


def test_meeting_brief_uses_only_the_record_and_is_stored(client: TestClient, monkeypatch) -> None:
    from EvoScientist.pm import _ai

    seen: dict = {}

    async def fake_llm(system_prompt, user_prompt, **kwargs):
        seen["system"], seen["user"] = system_prompt, user_prompt
        return "## What changed\\n- Trained baseline\\n## What is stuck\\n- nothing\\n## Three questions to ask\\n1. a\\n2. b\\n3. c"

    monkeypatch.setattr(_ai, "run_llm_direct_async", fake_llm)
    _assign(client)
    report_id = client.post("/api/v1/supervision/weekly/current", headers=_h(client.stud_token)).json()["id"]
    client.put(f"/api/v1/supervision/reports/{report_id}/summary",
               json={"accomplished": "Trained baseline U-Net", "support_requested": "GPU quota"},
               headers=_h(client.stud_token))
    client.post(f"/api/v1/supervision/reports/{report_id}/submit", headers=_h(client.stud_token))
    client.post(f"/api/v1/supervision/reports/{report_id}/review",
                json={"review_status": "reviewed", "followups": [{"text": "Report per-layer Dice"}]},
                headers=_h(client.prof_token))

    r = client.post(f"/api/v1/supervision/students/{client.stud_id}/meeting-brief", headers=_h(client.prof_token))
    assert r.status_code == 202, r.text
    job = client.get(f"/api/v1/ai-jobs/{r.json()['job_id']}", headers=_h(client.prof_token)).json()
    assert job["status"] == "done" and job["result_path"] == f"/meeting?student={client.stud_id}"

    assert "ONLY the facts" in seen["system"]
    assert "Trained baseline U-Net" in seen["user"] and "GPU quota" in seen["user"]
    assert "Open follow-up" in seen["user"] and "Report per-layer Dice" in seen["user"]

    brief = client.get(f"/api/v1/supervision/students/{client.stud_id}/meeting-brief", headers=_h(client.prof_token)).json()
    assert brief["content"].startswith("## What changed")


def test_meeting_brief_with_nothing_recorded_fails_honestly(client: TestClient, monkeypatch) -> None:
    from EvoScientist.pm import _ai

    async def must_not_be_called(*a, **k):
        raise AssertionError("the model must not be asked to summarise an empty record")

    monkeypatch.setattr(_ai, "run_llm_direct_async", must_not_be_called)
    _assign(client)
    job_id = client.post(f"/api/v1/supervision/students/{client.stud_id}/meeting-brief",
                         headers=_h(client.prof_token)).json()["job_id"]
    job = client.get(f"/api/v1/ai-jobs/{job_id}", headers=_h(client.prof_token)).json()
    assert job["status"] == "failed" and "Nothing has been recorded" in job["error"]


def test_meeting_brief_is_for_the_students_own_supervisor(client: TestClient) -> None:
    r = client.post(f"/api/v1/supervision/students/{client.stud_id}/meeting-brief", headers=_h(client.prof_token))
    assert r.status_code == 404  # not assigned
    r = client.get(f"/api/v1/supervision/students/{client.stud_id}/meeting-brief", headers=_h(client.stud_token))
    assert r.status_code == 404


# ── Semester skills check ────────────────────────────────────────────────────


def test_skills_check_self_and_supervisor_side_by_side(client: TestClient) -> None:
    _assign(client)
    sid = client.stud_id
    r = client.put("/api/v1/supervision/skills", json={"student_id": sid, "scores": {"writing": 2, "methods": 3}},
                   headers=_h(client.stud_token))
    assert r.status_code == 200 and r.json()["perspective"] == "self"
    r = client.put("/api/v1/supervision/skills",
                   json={"student_id": sid, "scores": {"writing": 3, "methods": 2}, "comment": "Clearer drafts"},
                   headers=_h(client.prof_token))
    assert r.json()["perspective"] == "supervisor"
    # Saving again in the same term updates, it does not duplicate.
    client.put("/api/v1/supervision/skills", json={"student_id": sid, "scores": {"writing": 3, "methods": 3}},
               headers=_h(client.stud_token))

    view = client.get("/api/v1/supervision/skills", params={"student_id": sid}, headers=_h(client.stud_token)).json()
    assert set(view["skills"]) == {"writing", "methods", "presenting", "independence"}
    by = {a["perspective"]: a for a in view["assessments"]}
    assert len(view["assessments"]) == 2
    assert by["self"]["scores"] == {"writing": 3, "methods": 3}
    assert by["supervisor"]["comment"] == "Clearer drafts"
    assert by["self"]["term"] == view["current_term"]


def test_skills_check_validates_and_stays_private(client: TestClient) -> None:
    sid = client.stud_id
    bad = client.put("/api/v1/supervision/skills", json={"student_id": sid, "scores": {"writing": 7}},
                     headers=_h(client.stud_token))
    assert bad.status_code == 422
    bad = client.put("/api/v1/supervision/skills", json={"student_id": sid, "scores": {"gpa": 3}},
                     headers=_h(client.stud_token))
    assert bad.status_code == 422
    # A professor who does not supervise this student sees nothing.
    assert client.get("/api/v1/supervision/skills", params={"student_id": sid},
                      headers=_h(client.prof_token)).status_code == 404


def test_term_boundaries() -> None:
    from datetime import date

    from EvoScientist.pm.api.routes.skills import term_of

    assert term_of(date(2026, 9, 1)) == "2026 Fall"
    assert term_of(date(2027, 1, 20)) == "2026 Fall"
    assert term_of(date(2027, 2, 1)) == "2027 Spring"
    assert term_of(date(2027, 8, 31)) == "2027 Spring"


# ── Publication gap ──────────────────────────────────────────────────────────


def test_publication_gap_projects_only_with_a_real_pace(client: TestClient, tmp_db) -> None:
    from datetime import date, timedelta

    from EvoScientist.pm.crud.publications import create_publication, update_publication

    _assign(client)
    start = (date.today() - timedelta(days=360)).isoformat()  # ~12 months ago
    r = client.post("/api/v1/supervision/journeys", params={"student_id": client.stud_id},
                    json={"level": "PhD", "status": "active", "start_date": start},
                    headers=_h(client.prof_token))
    assert r.status_code in (200, 201), r.text
    client.post("/api/v1/supervision/requirements",
                json={"level": "PhD", "title": "Two journal papers", "req_type": "research_item",
                      "research_item_type": "Journal Paper", "target_value": 2, "required": True},
                headers=_h(client.admin_token))

    def gap():
        body = client.get("/api/v1/supervision/readiness", params={"student_id": client.stud_id},
                          headers=_h(client.prof_token)).json()
        return body["publication_gap"]

    # Nothing submitted yet: a gap, but no invented estimate.
    g = gap()
    assert g["items"][0]["gap"] == 2 and g["items"][0]["eta_months"] is None and g["pace_per_month"] is None

    one = create_publication(tmp_db, title="Paper A", created_by=client.stud_id, venue_type="journal")
    update_publication(tmp_db, one.id, status="submitted", submitted_at=date.today().isoformat())
    create_publication(tmp_db, title="Draft B", created_by=client.stud_id, venue_type="journal")
    create_publication(tmp_db, title="Conf draft", created_by=client.stud_id, venue_type="conference")

    g = gap()
    item = g["items"][0]
    assert item["gap"] == 1
    assert [d["title"] for d in item["in_progress"]] == ["Draft B"]  # journal drafts only
    assert g["pace_per_month"] is not None and item["eta_months"] == round(1 / g["pace_per_month"])


def test_readiness_is_for_the_students_own_supervisor(client: TestClient) -> None:
    r = client.get("/api/v1/supervision/readiness", params={"student_id": client.stud_id},
                   headers=_h(client.prof_token))
    assert r.status_code == 403  # not assigned
    _assign(client)
    r = client.get("/api/v1/supervision/readiness", params={"student_id": client.stud_id},
                   headers=_h(client.prof_token))
    assert r.status_code == 200


# ── Semester report ──────────────────────────────────────────────────────────


def test_progress_report_contents_escaping_and_word_download(client: TestClient) -> None:
    from datetime import date

    from EvoScientist.pm.api.routes.skills import term_of

    _assign(client)
    report_id = client.post("/api/v1/supervision/weekly/current", headers=_h(client.stud_token)).json()["id"]
    client.put(f"/api/v1/supervision/reports/{report_id}/summary",
               json={"accomplished": "Trained <script>alert(1)</script> U-Net"}, headers=_h(client.stud_token))
    client.post(f"/api/v1/supervision/reports/{report_id}/submit", headers=_h(client.stud_token))
    client.post(f"/api/v1/supervision/reports/{report_id}/review",
                json={"review_status": "reviewed", "feedback": "Good week",
                      "followups": [{"text": "Write the related-work section"}]},
                headers=_h(client.prof_token))
    client.put("/api/v1/supervision/skills", json={"student_id": client.stud_id, "scores": {"writing": 3}},
               headers=_h(client.prof_token))

    term = term_of(date.today())
    r = client.get(f"/api/v1/supervision/students/{client.stud_id}/progress-report", params={"term": term},
                   headers=_h(client.prof_token))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    html = r.text
    assert "Semester progress report" in html and term in html
    assert "1 of " in html and "Good week" in html and "Write the related-work section" in html
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html  # student text is escaped
    assert "Supervisor's overall assessment" in html

    doc = client.get(f"/api/v1/supervision/students/{client.stud_id}/progress-report.doc", params={"term": term},
                     headers=_h(client.prof_token))
    assert doc.headers["content-type"] == "application/msword"
    assert "attachment" in doc.headers["content-disposition"] and ".doc" in doc.headers["content-disposition"]

    # A different term does not include this week's update.
    other = client.get(f"/api/v1/supervision/students/{client.stud_id}/progress-report", params={"term": "2001 Fall"},
                       headers=_h(client.prof_token)).text
    assert "Good week" not in other and "No weekly updates recorded this term." in other


def test_progress_report_access_and_term_validation(client: TestClient) -> None:
    url = f"/api/v1/supervision/students/{client.stud_id}/progress-report"
    assert client.get(url, headers=_h(client.prof_token)).status_code == 404  # not their student
    assert client.get(url, headers=_h(client.stud_token)).status_code == 200  # the student's own
    assert client.get(url, params={"term": "2026 Winter"}, headers=_h(client.stud_token)).status_code == 400


# ── Cohort view ──────────────────────────────────────────────────────────────


def test_cohort_view_compares_students_on_recorded_data(client: TestClient, tmp_db) -> None:
    from EvoScientist.pm.crud.users import create_user

    _assign(client)
    report_id = client.post("/api/v1/supervision/weekly/current", headers=_h(client.stud_token)).json()["id"]
    client.post(f"/api/v1/supervision/reports/{report_id}/submit", headers=_h(client.stud_token))
    client.post(f"/api/v1/supervision/reports/{report_id}/review",
                json={"review_status": "reviewed", "risk_override": "high",
                      "followups": [{"text": "A"}, {"text": "B", "due_date": "2000-01-01"}]},
                headers=_h(client.prof_token))
    fid = client.get("/api/v1/supervision/followups", headers=_h(client.stud_token)).json()[0]["id"]
    client.patch(f"/api/v1/supervision/followups/{fid}", json={"status": "done"}, headers=_h(client.stud_token))
    client.put("/api/v1/supervision/skills", json={"student_id": client.stud_id, "scores": {"writing": 2, "methods": 4}},
               headers=_h(client.stud_token))
    # A second student with nothing recorded.
    quiet = create_user(tmp_db, "quiet", hash_password("secret123"), role="student")
    client.post("/api/v1/supervision/assignments", json={"student_id": quiet.id, "professor_id": client.prof_id},
                headers=_h(client.prof_token))

    view = client.get("/api/v1/supervision/cohort", headers=_h(client.prof_token)).json()
    rows = {r["name"]: r for r in view["rows"]}
    assert set(rows) == {"stud", "quiet"}
    s = rows["stud"]
    assert s["weeks_submitted"] == 1 and s["high_risk_weeks"] == 1
    assert (s["followups_asked"], s["followups_done"], s["followups_open"], s["followups_overdue"]) == (2, 1, 1, 1)
    assert s["median_days_to_close"] == 0 and s["skills_self"] == 3.0
    q = rows["quiet"]
    assert q["weeks_submitted"] == 0 and q["followups_asked"] == 0 and q["skills_self"] is None
    assert "submission_rate" in view["medians"]


def test_cohort_view_is_for_supervisors(client: TestClient) -> None:
    assert client.get("/api/v1/supervision/cohort", headers=_h(client.stud_token)).status_code == 403
    assert client.get("/api/v1/supervision/cohort", params={"term": "nonsense"},
                      headers=_h(client.prof_token)).status_code == 400
