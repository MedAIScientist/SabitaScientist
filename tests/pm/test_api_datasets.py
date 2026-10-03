"""Tests for /datasets — the imaging-dataset governance chain (v2 storage model).

The invariant under test everywhere: releasing a PHI cohort takes TWO DISTINCT
HUMANS — a real lab PI and a different platform admin — and a project can never
be deleted while governance rows reference it.
"""

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
        role="professor",  # these users create and lead labs; only professors may
    )
    token = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    ).json()["token"]
    return user, token


def _future(days=365) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).date().isoformat()


def _scaffold(client, tmp_db):
    """A lab with a PI, an ms member, a project owned by the PI, and one
    admin-approved IRB on that project. Returns a dict of the pieces."""
    pi, pi_token = _make_user(client, tmp_db, "pi_user")
    lab = client.post(
        "/api/v1/labs", json={"name": "Ankle Lab"}, headers=_auth(pi_token)
    ).json()
    ms, ms_token = _make_user(client, tmp_db, "ms_student")
    client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": ms.id, "role": "ms"},
        headers=_auth(pi_token),
    )
    project = client.post(
        "/api/v1/projects",
        json={"name": "Ankle segmentation", "lab_id": lab["id"]},
        headers=_auth(pi_token),
    ).json()
    admin, admin_token = _make_user(client, tmp_db, "root", is_admin=True)
    irb = client.post(
        "/api/v1/irb",
        json={
            "project_id": project["id"],
            "institution": "Medipol",
            "protocol_number": "2026/42",
            "title": "Ankle study",
            "status": "submitted",
        },
        headers=_auth(pi_token),
    ).json()
    r = client.put(
        f"/api/v1/irb/{irb['id']}",
        json={
            "status": "approved",
            "approval_date": "2026-08-01",
            "expiry_date": _future(),
            "documents": ["irb-2026-42.pdf"],
        },
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    return {
        "lab": lab,
        "pi": pi,
        "pi_token": pi_token,
        "ms": ms,
        "ms_token": ms_token,
        "project": project,
        "admin": admin,
        "admin_token": admin_token,
        "irb": irb,
    }


def _draft(client, s, **over):
    body = {
        "name": "DX ayak/bilek 2019-2025",
        "purpose": "segmentation cohort",
        "lab_id": s["lab"]["id"],
        "modality": "DX",
        "accession_list": ["BGC1166557"],
        "estimated_bytes": 500_000_000,
        "irb_ids": [s["irb"]["id"]],
    }
    body.update(over)
    return client.post("/api/v1/datasets", json=body, headers=_auth(s["pi_token"]))


def _approved_dataset(client, s):
    """Walk one dataset through the full two-human chain."""
    ds = _draft(client, s).json()
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["pi_token"])
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/admin-approve",
        json={"retention_until": _future(730)},
        headers=_auth(s["admin_token"]),
    )
    assert r.status_code == 200, r.text
    return r.json()


# ── drafting ──────────────────────────────────────────────────────────────────


def test_lab_member_drafts_dataset(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    r = _draft(client, s)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["irb_ids"] == [s["irb"]["id"]]
    assert body["bucket"] is None  # no bucket before admin approval


def test_outsider_cannot_draft(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    _out, out_token = _make_user(client, tmp_db, "outsider")
    r = client.post(
        "/api/v1/datasets",
        json={
            "name": "x",
            "purpose": "y",
            "lab_id": s["lab"]["id"],
            "accession_list": ["A1"],
        },
        headers=_auth(out_token),
    )
    assert r.status_code == 403


def test_draft_requires_real_lab_and_accessions(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    assert _draft(client, s, lab_id="nope").status_code == 400
    assert _draft(client, s, accession_list=[]).status_code == 400
    assert _draft(client, s, irb_ids=["ghost"]).status_code == 400


# ── the PI leg ────────────────────────────────────────────────────────────────


def test_ms_member_cannot_pi_approve(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _draft(client, s).json()
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["ms_token"])
    )
    assert r.status_code == 403


def test_platform_admin_does_not_substitute_for_the_pi(client, tmp_db) -> None:
    """The one place the admin-superuser rule stops: PHI accountability is the lab's."""
    s = _scaffold(client, tmp_db)
    ds = _draft(client, s).json()
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["admin_token"])
    )
    assert r.status_code == 403
    assert "platform admin does not substitute" in r.json()["detail"]


def test_pi_approve_requires_an_irb(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _draft(client, s, irb_ids=[]).json()
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["pi_token"])
    )
    assert r.status_code == 409


# ── the admin leg ─────────────────────────────────────────────────────────────


def test_admin_approve_needs_two_distinct_humans(client, tmp_db) -> None:
    """An admin who did the PI leg (admin who is also lab PI) cannot also do the
    admin leg — one person can never walk a cohort out alone."""
    s = _scaffold(client, tmp_db)
    # make an admin who is ALSO the lab PI
    adminpi, adminpi_token = _make_user(client, tmp_db, "adminpi", is_admin=True)
    client.post(
        f"/api/v1/labs/{s['lab']['id']}/members",
        json={"user_id": adminpi.id, "role": "pi"},
        headers=_auth(s["pi_token"]),
    )
    ds = _draft(client, s).json()
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(adminpi_token)
    )
    assert r.status_code == 200
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/admin-approve",
        json={"retention_until": _future(730)},
        headers=_auth(adminpi_token),
    )
    assert r.status_code == 403
    # a DIFFERENT admin succeeds
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/admin-approve",
        json={"retention_until": _future(730)},
        headers=_auth(s["admin_token"]),
    )
    assert r.status_code == 200
    assert r.json()["bucket"] == f"ds-{ds['id']}"


def test_admin_approve_refuses_unapproved_or_expired_irb(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    # an IRB still in 'submitted'
    sub_irb = client.post(
        "/api/v1/irb",
        json={
            "project_id": s["project"]["id"],
            "institution": "Medipol",
            "protocol_number": "2026/43",
            "title": "unapproved",
            "status": "submitted",
        },
        headers=_auth(s["pi_token"]),
    ).json()
    ds = _draft(client, s, irb_ids=[sub_irb["id"]]).json()
    client.post(f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["pi_token"]))
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/admin-approve",
        json={"retention_until": _future(730)},
        headers=_auth(s["admin_token"]),
    )
    assert r.status_code == 409
    assert "not in status 'approved'" in r.json()["detail"]


def test_admin_approve_requires_retention(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _draft(client, s).json()
    client.post(f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["pi_token"]))
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/admin-approve",
        json={},
        headers=_auth(s["admin_token"]),
    )
    assert r.status_code == 409
    assert "retention_until" in r.json()["detail"]


def test_non_admin_cannot_admin_approve(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _draft(client, s).json()
    client.post(f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["pi_token"]))
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/admin-approve",
        json={"retention_until": _future(730)},
        headers=_auth(s["pi_token"]),
    )
    assert r.status_code == 403


# ── lifecycle transitions ─────────────────────────────────────────────────────


def test_transitions_follow_the_state_machine(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)
    t = lambda body: client.post(  # noqa: E731
        f"/api/v1/datasets/{ds['id']}/transition",
        json=body,
        headers=_auth(s["admin_token"]),
    )
    # sealed straight from approved is refused
    assert t({"status": "sealed", "content_root_sha256": "a" * 64}).status_code == 409
    assert t({"status": "delivering"}).status_code == 200
    # sealing without a merkle root is refused
    assert t({"status": "sealed"}).status_code == 409
    r = t({"status": "sealed", "content_root_sha256": "a" * 64})
    assert r.status_code == 200
    assert r.json()["sealed_at"]
    assert t({"status": "expired"}).status_code == 200


# ── grants ────────────────────────────────────────────────────────────────────


def test_grant_takes_owning_pi_then_a_different_admin(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)
    # a lab-less project — your orphan-project question, answered by grants
    orphan_owner, orphan_token = _make_user(client, tmp_db, "orphan_owner")
    orphan = client.post(
        "/api/v1/projects", json={"name": "orphan"}, headers=_auth(orphan_token)
    ).json()
    # platform admin cannot do the PI leg
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/grants",
        json={"project_id": orphan["id"]},
        headers=_auth(s["admin_token"]),
    )
    assert r.status_code == 403
    # the owning PI proposes -> pending, not active
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/grants",
        json={"project_id": orphan["id"]},
        headers=_auth(s["pi_token"]),
    )
    assert r.status_code == 201
    grant = r.json()
    assert grant["active"] is False
    # a second unrevoked proposal for the same project is refused
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/grants",
        json={"project_id": orphan["id"]},
        headers=_auth(s["pi_token"]),
    )
    assert r.status_code == 409
    # activation is admin-only and must be a different human than the proposer
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/grants/{grant['id']}/approve",
        headers=_auth(s["pi_token"]),
    )
    assert r.status_code == 403
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/grants/{grant['id']}/approve",
        headers=_auth(s["admin_token"]),
    )
    assert r.status_code == 200
    assert r.json()["active"] is True


def test_grant_needs_an_approved_dataset_and_a_real_project(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _draft(client, s).json()  # still draft
    r = client.post(
        f"/api/v1/datasets/{ds['id']}/grants",
        json={"project_id": s["project"]["id"]},
        headers=_auth(s["pi_token"]),
    )
    assert r.status_code == 409
    approved = _approved_dataset(client, s)
    r = client.post(
        f"/api/v1/datasets/{approved['id']}/grants",
        json={"project_id": "ghost"},
        headers=_auth(s["pi_token"]),
    )
    assert r.status_code == 400


def test_revoke_is_one_human_and_idempotent(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)
    grant = client.post(
        f"/api/v1/datasets/{ds['id']}/grants",
        json={"project_id": s["project"]["id"]},
        headers=_auth(s["pi_token"]),
    ).json()
    client.post(
        f"/api/v1/datasets/{ds['id']}/grants/{grant['id']}/approve",
        headers=_auth(s["admin_token"]),
    )
    url = f"/api/v1/datasets/{ds['id']}/grants/{grant['id']}"
    assert client.delete(url, headers=_auth(s["pi_token"])).status_code == 204
    assert client.delete(url, headers=_auth(s["pi_token"])).status_code == 204
    got = client.get(
        f"/api/v1/datasets/{ds['id']}", headers=_auth(s["pi_token"])
    ).json()
    assert got["grants"][0]["revoked_at"]
    assert got["grants"][0]["active"] is False


# ── visibility ────────────────────────────────────────────────────────────────


def test_outsiders_get_404_and_empty_lists(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)
    _out, out_token = _make_user(client, tmp_db, "curious")
    r = client.get(f"/api/v1/datasets/{ds['id']}", headers=_auth(out_token))
    assert r.status_code == 404
    r = client.get("/api/v1/datasets", headers=_auth(out_token))
    assert r.json() == []
    # the ms lab member DOES see it
    r = client.get(f"/api/v1/datasets/{ds['id']}", headers=_auth(s["ms_token"]))
    assert r.status_code == 200


# ── the desired-state push document ───────────────────────────────────────────


def test_desired_state_document_shape(client, tmp_db) -> None:
    from gazzali.platform_push import build_desired_state

    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)
    pending = client.post(
        f"/api/v1/datasets/{ds['id']}/grants",
        json={"project_id": s["project"]["id"]},
        headers=_auth(s["pi_token"]),
    ).json()
    doc = build_desired_state(tmp_db, ds["id"])
    assert doc["dataset"]["bucket"] == f"ds-{ds['id']}"
    assert doc["dataset"]["status"] == "approved"
    assert doc["grants"] == []  # pending grants grant NOTHING anywhere
    client.post(
        f"/api/v1/datasets/{ds['id']}/grants/{pending['id']}/approve",
        headers=_auth(s["admin_token"]),
    )
    doc2 = build_desired_state(tmp_db, ds["id"])
    assert doc2["generation"] > doc["generation"]
    # The exact wire shape, pinned on purpose: platform-control rejects unknown fields, so a
    # field added here without deploying the cluster side first would 400 every push.
    assert doc2["grants"] == [
        {
            "project_id": s["project"]["id"],
            "expires_at": "",
            "revoked": False,
            "project_name": s["project"]["name"],
        }
    ]
    client.delete(
        f"/api/v1/datasets/{ds['id']}/grants/{pending['id']}",
        headers=_auth(s["admin_token"]),
    )
    doc3 = build_desired_state(tmp_db, ds["id"])
    assert doc3["grants"][0]["revoked"] is True
    assert doc3["generation"] > doc2["generation"]


def test_push_is_a_noop_without_env(client, tmp_db, monkeypatch) -> None:
    from gazzali.platform_push import push_dataset

    monkeypatch.delenv("MEDAI_PLATFORM_CONTROL_URL", raising=False)
    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)
    assert push_dataset(tmp_db, ds["id"]) is None


# ── the project-delete guard ──────────────────────────────────────────────────


def test_project_with_governance_rows_cannot_be_deleted(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    # the scaffold project already holds an IRB row
    r = client.delete(
        f"/api/v1/projects/{s['project']['id']}", headers=_auth(s["pi_token"])
    )
    assert r.status_code == 409
    assert "irb_approvals" in r.json()["detail"]
    # a clean project still deletes fine
    clean = client.post(
        "/api/v1/projects", json={"name": "scratch"}, headers=_auth(s["pi_token"])
    ).json()
    r = client.delete(
        f"/api/v1/projects/{clean['id']}", headers=_auth(s["pi_token"])
    )
    assert r.status_code == 204


def test_project_with_dataset_grant_cannot_be_deleted(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)
    target = client.post(
        "/api/v1/projects", json={"name": "granted"}, headers=_auth(s["pi_token"])
    ).json()
    client.post(
        f"/api/v1/datasets/{ds['id']}/grants",
        json={"project_id": target["id"]},
        headers=_auth(s["pi_token"]),
    )
    r = client.delete(
        f"/api/v1/projects/{target['id']}", headers=_auth(s["pi_token"])
    )
    assert r.status_code == 409
    assert "dataset_grants" in r.json()["detail"]


# ── increment 4: annotation staging is a HUMAN request with real preconditions ─


def test_annotate_grant_needs_renders_and_a_provisioned_cvat_project(client, tmp_db) -> None:
    from gazzali.crud.cvat import create_cvat_project

    s = _scaffold(client, tmp_db)
    # a dataset approved WITHOUT renders can never carry an annotation grant —
    # CVAT cannot display DICOM, so the request would be a trap
    ds = _draft(client, s, renders=False).json()
    client.post(f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["pi_token"]))
    client.post(f"/api/v1/datasets/{ds['id']}/admin-approve",
                json={"retention_until": _future(730)}, headers=_auth(s["admin_token"]))
    r = client.post(f"/api/v1/datasets/{ds['id']}/grants",
                    json={"project_id": s["project"]["id"], "annotate": True},
                    headers=_auth(s["pi_token"]))
    assert r.status_code == 409 and "renders" in r.json()["detail"]

    # with renders, annotate still needs a provisioned CVAT project first
    ds2 = _approved_dataset(client, s)
    r = client.post(f"/api/v1/datasets/{ds2['id']}/grants",
                    json={"project_id": s["project"]["id"], "annotate": True},
                    headers=_auth(s["pi_token"]))
    assert r.status_code == 400 and "provision" in r.json()["detail"]

    # provisioned -> the grant records the CONCRETE CVAT id and the task size
    create_cvat_project(tmp_db, s["project"]["id"], 42, "cv", s["pi"].id)
    r = client.post(f"/api/v1/datasets/{ds2['id']}/grants",
                    json={"project_id": s["project"]["id"], "annotate": True, "task_size": 20},
                    headers=_auth(s["pi_token"]))
    assert r.status_code == 201
    g = r.json()
    assert g["cvat_project_id"] == 42 and g["task_size"] == 20

    # ...and it travels in the push document
    from gazzali.platform_push import build_desired_state
    client.post(f"/api/v1/datasets/{ds2['id']}/grants/{g['id']}/approve",
                headers=_auth(s["admin_token"]))
    doc = build_desired_state(tmp_db, ds2["id"])
    assert doc["dataset"]["renders"] is True
    assert doc["grants"][0]["annotate"] == {"cvat_project_id": 42, "task_size": 20}


# ── Requests tracked per project, and the approvals inbox ────────────────────


def _steps(client, s, token=None):
    r = client.get(
        f"/api/v1/projects/{s['project']['id']}/dataset-requests",
        headers=_auth(token or s["pi_token"]),
    )
    assert r.status_code == 200, r.text
    return r.json()


def _inbox(client, token):
    r = client.get("/api/v1/imaging/inbox", headers=_auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _current(req):
    return next((st["key"] for st in req["steps"] if st["state"] == "current"), "ready")


def test_request_is_tracked_for_its_project_through_every_step(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    pid = s["project"]["id"]
    ds = _draft(client, s, project_id=pid).json()
    assert ds["project_id"] == pid

    (req,) = _steps(client, s)
    assert _current(req) == "pi" and req["waiting_on"] == "Lab PI"
    assert "accession_list" not in req and req["accession_count"] == 1  # metadata only

    # The PI sees it in the inbox, with nothing blocking.
    (item,) = _inbox(client, s["pi_token"])
    assert item["action"] == "pi-approve" and item["blockers"] == []
    client.post(f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["pi_token"]))
    assert _current(_steps(client, s)[0]) == "admin"

    # The admin sees the admin step; the PI no longer has anything.
    (item,) = _inbox(client, s["admin_token"])
    assert item["action"] == "admin-approve" and item["blockers"] == []
    assert _inbox(client, s["pi_token"]) == []
    r = client.post(f"/api/v1/datasets/{ds['id']}/admin-approve",
                    json={"retention_until": _future(700)}, headers=_auth(s["admin_token"]))
    assert r.status_code == 200, r.text
    assert _steps(client, s)[0]["waiting_on"] == "Lab PI (share with the project)"

    # Sharing with the requesting project is offered to the PI, then activated by the admin.
    (item,) = _inbox(client, s["pi_token"])
    assert item["action"] == "propose-grant" and item["project_id"] == pid
    grant = client.post(f"/api/v1/datasets/{ds['id']}/grants", json={"project_id": pid},
                        headers=_auth(s["pi_token"])).json()
    assert _steps(client, s)[0]["waiting_on"] == "Platform admin (activate access)"
    (item,) = [i for i in _inbox(client, s["admin_token"]) if i["action"] == "approve-grant"]
    assert item["grant_id"] == grant["id"]
    client.post(f"/api/v1/datasets/{ds['id']}/grants/{grant['id']}/approve", headers=_auth(s["admin_token"]))
    req = _steps(client, s)[0]
    assert _current(req) == "delivery" and req["waiting_on"] == "Delivery from PACS"


def test_inbox_explains_why_a_step_is_blocked(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _draft(client, s, irb_ids=[]).json()
    (item,) = _inbox(client, s["pi_token"])
    assert item["action"] == "pi-approve"
    assert item["blockers"] == ["Link an IRB approval first."]
    assert ds["id"] == item["dataset_id"]


def test_admin_who_approved_as_pi_is_not_offered_the_admin_step(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _draft(client, s).json()
    client.post(f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["pi_token"]))
    assert [i["action"] for i in _inbox(client, s["admin_token"])] == ["admin-approve"]
    assert _inbox(client, s["ms_token"]) == []  # a student approves nothing


def test_requesting_for_a_project_needs_write_access_to_it(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    body = {
        "name": "x", "purpose": "y", "lab_id": s["lab"]["id"], "accession_list": ["A1"],
        "irb_ids": [s["irb"]["id"]], "project_id": s["project"]["id"],
    }
    # The student is a lab member but not on the project.
    r = client.post("/api/v1/datasets", json=body, headers=_auth(s["ms_token"]))
    assert r.status_code == 403


def test_non_members_cannot_see_a_projects_requests(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    _draft(client, s, project_id=s["project"]["id"])
    r = client.get(f"/api/v1/projects/{s['project']['id']}/dataset-requests", headers=_auth(s["ms_token"]))
    assert r.status_code == 404
