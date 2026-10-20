"""The IRB lifecycle exactly as the IRB page drives it: these are the request bodies
pages/IRBPage.tsx sends, so a change to the API contract fails here instead of in
the browser. Before the page had these controls, the only way past 'draft' was a
hand-written PUT from the browser console."""

from datetime import UTC, datetime, timedelta


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_user(client, tmp_db, username, password="pw", is_admin=False):
    from gazzali.auth import hash_password
    from gazzali.crud.users import create_user

    user = create_user(
        tmp_db,
        username=username,
        password_hash=hash_password(password),
        is_admin=is_admin,
    )
    token = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    ).json()["token"]
    return user, token


def _future(days=365) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).date().isoformat()


def _draft(client, tmp_db):
    """The create form: project, title, institution, protocol — no status, so a draft."""
    _, owner_token = _make_user(client, tmp_db, "proj_owner")
    project = client.post(
        "/api/v1/projects", json={"name": "Ankle study"}, headers=_auth(owner_token)
    ).json()
    _, admin_token = _make_user(client, tmp_db, "root", is_admin=True)
    r = client.post(
        "/api/v1/irb",
        json={
            "project_id": project["id"],
            "title": "Ankle DX study",
            "institution": "Medipol",
            "protocol_number": "E-1",
        },
        headers=_auth(owner_token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "draft"
    return r.json()["id"], owner_token, admin_token


def _evidence(**over):
    body = {
        "approval_date": "2026-10-01",
        "expiry_date": _future(),
        "documents": ["EK-2026/14"],
    }
    body.update(over)
    return body


def test_submit_then_approve_with_the_evidence_from_the_submission(client, tmp_db):
    iid, owner_token, admin_token = _draft(client, tmp_db)

    r = client.put(
        f"/api/v1/irb/{iid}",
        json={"status": "submitted", **_evidence()},
        headers=_auth(owner_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "submitted"

    # The approve form arrives pre-filled from the submission and resends it.
    r = client.put(
        f"/api/v1/irb/{iid}",
        json={"status": "approved", **_evidence()},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    assert body["approved_by"]
    assert body["approved_at"]
    assert body["documents"] == ["EK-2026/14"]


def test_the_writer_withdraws_a_submission(client, tmp_db):
    iid, owner_token, _ = _draft(client, tmp_db)
    client.put(f"/api/v1/irb/{iid}", json={"status": "submitted", **_evidence()}, headers=_auth(owner_token))
    r = client.put(f"/api/v1/irb/{iid}", json={"status": "draft"}, headers=_auth(owner_token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "draft"


def test_a_rejection_carries_the_reason_in_notes(client, tmp_db):
    iid, owner_token, admin_token = _draft(client, tmp_db)
    client.put(f"/api/v1/irb/{iid}", json={"status": "submitted", **_evidence()}, headers=_auth(owner_token))
    r = client.put(
        f"/api/v1/irb/{iid}",
        json={"status": "rejected", "notes": "Rejected 2026-10-16: decision letter missing"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"
    assert "decision letter missing" in r.json()["notes"]

    # Resubmit (the page offers it on rejected records) is a writer move.
    r = client.put(f"/api/v1/irb/{iid}", json={"status": "submitted", **_evidence()}, headers=_auth(owner_token))
    assert r.status_code == 200, r.text


def test_the_admin_ends_an_approved_record_by_status_alone(client, tmp_db):
    iid, owner_token, admin_token = _draft(client, tmp_db)
    client.put(f"/api/v1/irb/{iid}", json={"status": "submitted", **_evidence()}, headers=_auth(owner_token))
    client.put(f"/api/v1/irb/{iid}", json={"status": "approved", **_evidence()}, headers=_auth(admin_token))
    r = client.put(f"/api/v1/irb/{iid}", json={"status": "expired"}, headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "expired"


def test_a_writer_close_is_accepted_on_a_draft(client, tmp_db):
    iid, owner_token, _ = _draft(client, tmp_db)
    r = client.put(f"/api/v1/irb/{iid}", json={"status": "closed"}, headers=_auth(owner_token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "closed"


def test_the_controls_the_page_hides_are_refused_by_the_server_too(client, tmp_db):
    """The page never offers these; the server must refuse them regardless."""
    iid, owner_token, admin_token = _draft(client, tmp_db)
    client.put(f"/api/v1/irb/{iid}", json={"status": "submitted", **_evidence()}, headers=_auth(owner_token))
    r = client.put(f"/api/v1/irb/{iid}", json={"status": "approved", **_evidence()}, headers=_auth(owner_token))
    assert r.status_code == 403
    r = client.put(
        f"/api/v1/irb/{iid}",
        json={"status": "approved", **_evidence(expiry_date="2020-01-01")},
        headers=_auth(admin_token),
    )
    assert r.status_code == 409
