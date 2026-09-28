"""Tests for the IRB lockdown: no self-service approvals, immutable once approved,
append-only forever. Before this, any authenticated user could mint a back-dated
'approved' IRB row — the precondition for releasing PHI — and delete it afterwards."""

from datetime import UTC, datetime, timedelta


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_user(client, tmp_db, username, password="pw", is_admin=False):
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user

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


def _setup(client, tmp_db):
    owner, owner_token = _make_user(client, tmp_db, "proj_owner")
    project = client.post(
        "/api/v1/projects", json={"name": "Ankle study"}, headers=_auth(owner_token)
    ).json()
    admin, admin_token = _make_user(client, tmp_db, "root", is_admin=True)
    return owner, owner_token, project, admin, admin_token


def _irb_body(project_id, **over):
    body = {
        "project_id": project_id,
        "institution": "Medipol",
        "protocol_number": "2026/42",
        "title": "Ankle study",
        "status": "submitted",
    }
    body.update(over)
    return body


# ── creation ──────────────────────────────────────────────────────────────────


def test_cannot_be_born_approved(client, tmp_db) -> None:
    _o, owner_token, project, _a, _at = _setup(client, tmp_db)
    r = client.post(
        "/api/v1/irb",
        json=_irb_body(project["id"], status="approved"),
        headers=_auth(owner_token),
    )
    assert r.status_code == 422  # schema refuses the value outright


def test_creation_requires_project_write(client, tmp_db) -> None:
    _o, _ot, project, _a, _at = _setup(client, tmp_db)
    _stranger, stranger_token = _make_user(client, tmp_db, "stranger")
    r = client.post(
        "/api/v1/irb", json=_irb_body(project["id"]), headers=_auth(stranger_token)
    )
    assert r.status_code == 403
    r = client.post(
        "/api/v1/irb", json=_irb_body("ghost"), headers=_auth(stranger_token)
    )
    assert r.status_code == 400


def test_project_owner_can_draft_and_submit(client, tmp_db) -> None:
    _o, owner_token, project, _a, _at = _setup(client, tmp_db)
    r = client.post(
        "/api/v1/irb", json=_irb_body(project["id"]), headers=_auth(owner_token)
    )
    assert r.status_code == 201
    assert r.json()["status"] == "submitted"


# ── the decision is admin-only, from submitted, with evidence ────────────────


def test_non_admin_cannot_approve(client, tmp_db) -> None:
    _o, owner_token, project, _a, _at = _setup(client, tmp_db)
    irb = client.post(
        "/api/v1/irb", json=_irb_body(project["id"]), headers=_auth(owner_token)
    ).json()
    r = client.put(
        f"/api/v1/irb/{irb['id']}",
        json={"status": "approved", "approval_date": "2026-08-01",
              "expiry_date": _future(), "documents": ["x.pdf"]},
        headers=_auth(owner_token),
    )
    assert r.status_code == 403


def test_draft_cannot_be_approved_directly(client, tmp_db) -> None:
    _o, owner_token, project, _a, admin_token = _setup(client, tmp_db)
    irb = client.post(
        "/api/v1/irb",
        json=_irb_body(project["id"], status="draft"),
        headers=_auth(owner_token),
    ).json()
    r = client.put(
        f"/api/v1/irb/{irb['id']}",
        json={"status": "approved", "approval_date": "2026-08-01",
              "expiry_date": _future(), "documents": ["x.pdf"]},
        headers=_auth(admin_token),
    )
    assert r.status_code == 409


def test_approval_needs_dates_and_documents(client, tmp_db) -> None:
    _o, owner_token, project, _a, admin_token = _setup(client, tmp_db)
    irb = client.post(
        "/api/v1/irb", json=_irb_body(project["id"]), headers=_auth(owner_token)
    ).json()
    put = lambda body: client.put(  # noqa: E731
        f"/api/v1/irb/{irb['id']}", json=body, headers=_auth(admin_token)
    )
    assert put({"status": "approved"}).status_code == 409  # no dates, no docs
    assert (
        put({"status": "approved", "approval_date": "2026-08-01",
             "expiry_date": "2020-01-01", "documents": ["x.pdf"]}).status_code
        == 409
    )  # expiry in the past
    r = put({"status": "approved", "approval_date": "2026-08-01",
             "expiry_date": _future(), "documents": ["x.pdf"]})
    assert r.status_code == 200
    body = r.json()
    assert body["approved_by"] is not None  # WHO approved is recorded
    assert body["approved_at"] is not None


# ── approved rows are sealed ──────────────────────────────────────────────────


def _approved_irb(client, tmp_db):
    _o, owner_token, project, _a, admin_token = _setup(client, tmp_db)
    irb = client.post(
        "/api/v1/irb", json=_irb_body(project["id"]), headers=_auth(owner_token)
    ).json()
    client.put(
        f"/api/v1/irb/{irb['id']}",
        json={"status": "approved", "approval_date": "2026-08-01",
              "expiry_date": _future(), "documents": ["x.pdf"]},
        headers=_auth(admin_token),
    )
    return irb, owner_token, admin_token


def test_approved_irb_is_immutable(client, tmp_db) -> None:
    irb, owner_token, admin_token = _approved_irb(client, tmp_db)
    # the writer who created it cannot touch it any more
    r = client.put(
        f"/api/v1/irb/{irb['id']}",
        json={"notes": "sneaky edit"},
        headers=_auth(owner_token),
    )
    assert r.status_code == 403
    # even an admin cannot edit fields — only expire/close
    r = client.put(
        f"/api/v1/irb/{irb['id']}",
        json={"protocol_number": "changed"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 403
    r = client.put(
        f"/api/v1/irb/{irb['id']}", json={"status": "closed"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200


def test_delete_is_refused_for_everyone(client, tmp_db) -> None:
    irb, owner_token, admin_token = _approved_irb(client, tmp_db)
    assert (
        client.delete(f"/api/v1/irb/{irb['id']}", headers=_auth(owner_token)).status_code
        == 403
    )
    assert (
        client.delete(f"/api/v1/irb/{irb['id']}", headers=_auth(admin_token)).status_code
        == 403
    )
    # and the row is still there
    r = client.get(f"/api/v1/irb/{irb['id']}", headers=_auth(admin_token))
    assert r.status_code == 200
