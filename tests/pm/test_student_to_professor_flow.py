"""End to end: everything a student enters reaches their professor, who evaluates it,
and the student sees that evaluation. Another professor sees none of it.

Uses only the HTTP API, the way the two browsers would.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from gazzali.api.app import create_app
from gazzali.auth import hash_password
from gazzali.crud.users import create_user


def _login(c: TestClient, name: str) -> dict:
    tok = c.post("/api/v1/auth/login", json={"username": name, "password": "pw123456"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def test_student_input_reaches_the_professor_and_comes_back_evaluated(tmp_db: Path) -> None:
    kaya = create_user(tmp_db, "kaya", hash_password("pw123456"), email="kaya@medipol.edu.tr")
    create_user(tmp_db, "other", hash_password("pw123456"), email="other@medipol.edu.tr")
    stu = create_user(tmp_db, "melisa", hash_password("pw123456"), email="melisa@std.medipol.edu.tr")
    c = TestClient(create_app(tmp_db))
    prof, outsider, me = _login(c, "kaya"), _login(c, "other"), _login(c, "melisa")
    sv = "/api/v1/supervision"

    # 1. The student joins the professor's lab (request → PI approves), then gets a supervisor.
    lab = c.post("/api/v1/labs", json={"name": "Retina Lab"}, headers=prof).json()
    r = c.post(f"/api/v1/labs/{lab['id']}/join-requests", json={"lab_role": "phd", "message": "Hi"}, headers=me)
    assert r.status_code == 201, (lab, r.text)
    req = r.json()
    assert c.post(f"/api/v1/labs/{lab['id']}/join-requests/{req['id']}/approve", headers=prof).status_code == 200
    prof_id = kaya.id
    assert c.post(f"{sv}/assignments", json={"student_id": stu.id, "professor_id": prof_id}, headers=prof).status_code == 201
    assert [s["student_id"] for s in c.get(f"{sv}/my-students", headers=prof).json()] == [stu.id]

    # 2. The student writes this week's update and submits it.
    report = c.post(f"{sv}/weekly/current", headers=me).json()
    pub = c.post("/api/v1/publications", json={"title": "Class weighting in DR screening", "venue_type": "journal"}, headers=me).json()
    r = c.put(f"{sv}/reports/{report['id']}/items", headers=me, json={
        "item_title": pub["title"], "publication_id": pub["id"], "item_kind": "journal_paper",
        "progress_pct": 55, "status": "blocked", "blocker": "Waiting for the second annotator"})
    assert r.status_code in (200, 201), r.text
    assert c.put(f"{sv}/reports/{report['id']}/summary", headers=me, json={
        "accomplished": "Trained both models", "next_focus": "Write the results",
        "support_requested": "Need GPU time for the ablation"}).status_code == 200
    assert c.post(f"{sv}/reports/{report['id']}/submit", headers=me).json()["status"] == "submitted"
    c.post(f"{sv}/journeys", json={"level": "PhD", "status": "active", "thesis_title": "Robust retinal screening"}, headers=me)

    # 3. The professor sees all of it.
    seen = [x for x in c.get(f"{sv}/reports", headers=prof).json() if x["id"] == report["id"]]
    assert len(seen) == 1
    full = c.get(f"{sv}/reports/{report['id']}", headers=prof).json()
    assert full["support_requested"] == "Need GPU time for the ablation"
    assert full["accomplished"] == "Trained both models"
    item = full["items"][0]
    assert (item["progress_pct"], item.get("blocker")) == (55, "Waiting for the second annotator")
    assert any(i["id"] == pub["id"] for i in c.get(f"{sv}/research-items", params={"student_id": stu.id}, headers=prof).json())
    assert c.get(f"{sv}/journeys", params={"student_id": stu.id}, headers=prof).json()[0]["thesis_title"] == "Robust retinal screening"
    assert c.get(f"{sv}/readiness", params={"student_id": stu.id}, headers=prof).status_code == 200
    assert c.get(f"{sv}/analytics/professor", headers=prof).status_code == 200

    ov = c.get(f"{sv}/students/overview", headers=prof).json()
    assert [r["name"] for r in ov] == ["melisa"]
    row = ov[0]
    assert (row["this_week"], row["help_requested"], row["level"]) == ("submitted", "Need GPU time for the ablation", "PhD")
    assert row["blocked"] == [{"title": pub["title"], "blocker": "Waiting for the second annotator"}]
    assert {"asked for help", "1 blocked item", "1 update to review"} <= set(row["reasons"])
    assert c.get(f"{sv}/students/overview", headers=outsider).json() == []
    assert c.get(f"{sv}/students/overview", headers=me).status_code == 403

    # 4. Another professor sees nothing and cannot evaluate.
    assert all(x["student_id"] != stu.id for x in c.get(f"{sv}/reports", headers=outsider).json())
    assert c.get(f"{sv}/reports", params={"student_id": stu.id}, headers=outsider).status_code == 403
    assert c.post(f"{sv}/reports/{report['id']}/review", json={"feedback": "x"}, headers=outsider).status_code == 403

    # 5. The professor evaluates: feedback, risk, a follow-up with a deadline, attendance.
    due = (date.today() + timedelta(days=5)).isoformat()
    reviewed = c.post(f"{sv}/reports/{report['id']}/review", headers=prof, json={
        "review_status": "reviewed", "feedback": "Good progress; book the GPU for Friday.",
        "risk_override": "medium", "followups": [{"text": "Send the ROC curves", "due_date": due}]}).json()
    assert reviewed["review_status"] == "reviewed"
    week = report["week_start"]
    assert c.post(f"{sv}/attendance", params={"student_id": stu.id, "week": week}, json={"status": "attended"}, headers=prof).status_code in (200, 201)

    # 6. The student sees the evaluation and answers the follow-up.
    mine = c.get(f"{sv}/reports/{report['id']}", headers=me).json()
    assert mine["feedback"] == "Good progress; book the GPU for Friday."
    fu = c.get("/api/v1/supervision/followups", params={"status": "open"}, headers=me).json()
    assert [(f["text"], f["due_date"]) for f in fu] == [("Send the ROC curves", due)]
    assert c.patch(f"/api/v1/supervision/followups/{fu[0]['id']}", json={"status": "done", "note": "Uploaded to the project"}, headers=me).status_code == 200

    # 7. The professor sees the answer.
    back = [f for f in c.get("/api/v1/supervision/followups", headers=prof).json() if f["id"] == fu[0]["id"]][0]
    assert (back["status"], back["student_note"]) == ("done", "Uploaded to the project")
    after = c.get(f"{sv}/students/overview", headers=prof).json()[0]
    assert (after["this_week"], after["awaiting_review"], after["followups_open"]) == ("reviewed", 0, 0)
    assert "asked for help" not in after["reasons"]  # answered by the review
