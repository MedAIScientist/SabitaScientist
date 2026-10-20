"""Tests for /datasets — the imaging-dataset governance chain (v2 storage model).

The invariant under test everywhere: releasing a PHI cohort takes TWO DISTINCT
HUMANS — a real lab PI and a different platform admin — and a project can never
be deleted while governance rows reference it.
"""

from datetime import UTC, datetime, timedelta

import pytest


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
        email=f"{username}@test.local",  # the Curator hand-off finds a person's selections by e-mail
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


# A stand-in for Curator's hand-off (curator_bridge), so every request in this file is filed the
# real way: from a saved selection whose studies Medai's server fetches — never a typed list.
FAKE_CURATOR: dict = {}


@pytest.fixture(autouse=True)
def fake_curator(monkeypatch):
    from gazzali import curator_bridge

    FAKE_CURATOR.clear()
    FAKE_CURATOR.update(selections={}, submitted=[], retracted=[])

    def submit(selection_id, email, dataset_id):
        entry = FAKE_CURATOR["selections"].get(selection_id)
        if entry is None or entry.get("owner", email) != email:
            raise curator_bridge.CuratorRefused(404, "no such selection for this person")
        if entry.get("submitted"):
            raise curator_bridge.CuratorRefused(409, f"already requested by Medai ({email}) at earlier")
        entry["submitted"] = dataset_id
        FAKE_CURATOR["submitted"].append((selection_id, email, dataset_id))
        return {"accessions": entry["accessions"], "instances": entry.get("instances", 0),
                "instances_unknown": 0, "bytes_per_instance": entry.get("rate", 0),
                "bytes_per_render": entry.get("render_rate", 0),
                "bytes_per_object": entry.get("rate", 0),
                "rate_source": "measured" if entry.get("rate") else "none",
                "modality": entry.get("modality")}

    def retract(selection_id, email, dataset_id):
        FAKE_CURATOR["retracted"].append((selection_id, email, dataset_id))
        entry = FAKE_CURATOR["selections"].get(selection_id)
        if entry and entry.get("submitted") == dataset_id:
            entry["submitted"] = None
            return True
        return False

    monkeypatch.setattr(curator_bridge, "configured", lambda: True)
    monkeypatch.setattr(curator_bridge, "submit_selection", submit)
    monkeypatch.setattr(curator_bridge, "retract_selection", retract)
    return FAKE_CURATOR


def _saved_selection(accessions, **extra) -> str:
    """Register a saved Curator selection on the stand-in; returns its id."""
    import uuid as _uuid

    sel = f"sel_{_uuid.uuid4().hex}"
    FAKE_CURATOR["selections"][sel] = {"accessions": list(accessions), **extra}
    return sel


def _draft(client, s, token=None, **over):
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
    body["curator_selection_id"] = _saved_selection(body.pop("accession_list"))
    return client.post("/api/v1/datasets", json=body, headers=_auth(token or s["pi_token"]))


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
    # an empty selection: Curator hands over nothing, so nothing is filed (and the mark is undone)
    assert _draft(client, s, accession_list=[]).status_code == 409
    assert FAKE_CURATOR["retracted"], "the empty selection's mark was retracted"
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


def test_every_grant_names_its_project_for_the_person_revoking_it(client, tmp_db) -> None:
    """The lab page's revoke list shows WHICH project loses access; a bare project id is not
    something a PI can act on."""
    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)
    proposed = client.post(
        f"/api/v1/datasets/{ds['id']}/grants",
        json={"project_id": s["project"]["id"]},
        headers=_auth(s["pi_token"]),
    ).json()
    assert proposed["project_name"] == s["project"]["name"]
    approved = client.post(
        f"/api/v1/datasets/{ds['id']}/grants/{proposed['id']}/approve",
        headers=_auth(s["admin_token"]),
    ).json()
    assert approved["project_name"] == s["project"]["name"]
    listed = client.get(
        f"/api/v1/datasets?lab_id={ds['lab_id']}", headers=_auth(s["pi_token"])
    ).json()
    assert [g["project_name"] for d in listed for g in d["grants"]] == [s["project"]["name"]]


GIB = 1 << 30


def _pi_approved_without_estimate(client, s):
    ds = _draft(client, s, estimated_bytes=None).json()
    r = client.post(f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["pi_token"]))
    assert r.status_code == 200, r.text
    return ds


def test_the_admin_reserves_storage_at_approval_and_it_becomes_the_quota(client, tmp_db) -> None:
    """Without a reservation the delivered bucket has NO size limit (platform-control applies the
    pushed 0 as "none"), so an oversized cohort fills shared storage instead of stopping at its own
    ceiling. The admin, who holds Curator's estimate, sets it with the approval."""
    from gazzali.platform_push import build_desired_state

    s = _scaffold(client, tmp_db)
    ds = _pi_approved_without_estimate(client, s)
    inbox = client.get("/api/v1/imaging/inbox", headers=_auth(s["admin_token"])).json()
    assert [i["estimated_bytes"] for i in inbox if i["dataset_id"] == ds["id"]] == [None]

    r = client.post(f"/api/v1/datasets/{ds['id']}/admin-approve",
                    json={"retention_until": _future(730), "estimated_bytes": 3 * GIB},
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 200, r.text
    assert r.json()["estimated_bytes"] == 3 * GIB
    assert build_desired_state(tmp_db, ds["id"])["dataset"]["quota_bytes"] == 3 * GIB


def test_approval_without_a_reservation_keeps_the_requests_estimate(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)
    assert ds["estimated_bytes"] == 500_000_000


def test_storage_can_be_raised_later_but_never_lowered(client, tmp_db) -> None:
    """The remedy when Curator refuses a delivery that cannot fit. Raise-only, because the quota is
    applied exactly as pushed and one below what the bucket holds would stop its delivery."""
    from gazzali.platform_push import build_desired_state

    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)
    url = f"/api/v1/datasets/{ds['id']}/storage"

    assert client.post(url, json={"estimated_bytes": 2 * GIB},
                       headers=_auth(s["pi_token"])).status_code == 403, "platform admins only"
    r = client.post(url, json={"estimated_bytes": 2 * GIB}, headers=_auth(s["admin_token"]))
    assert r.status_code == 200, r.text
    assert build_desired_state(tmp_db, ds["id"])["dataset"]["quota_bytes"] == 2 * GIB

    lower = client.post(url, json={"estimated_bytes": GIB}, headers=_auth(s["admin_token"]))
    assert lower.status_code == 409
    assert "only be raised" in lower.text
    same = client.post(url, json={"estimated_bytes": 2 * GIB}, headers=_auth(s["admin_token"]))
    assert same.status_code == 409
    assert client.post(url, json={"estimated_bytes": 0},
                       headers=_auth(s["admin_token"])).status_code == 422


def test_storage_is_reserved_only_while_a_delivery_can_still_write(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    draft = _draft(client, s).json()
    r = client.post(f"/api/v1/datasets/{draft['id']}/storage", json={"estimated_bytes": 2 * GIB},
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 409, "before approval the reservation travels with the approval"
    ds = _approved_dataset(client, s)
    for target in ("delivering", "revoked"):
        client.post(f"/api/v1/datasets/{ds['id']}/transition", json={"status": target},
                    headers=_auth(s["admin_token"]))
    r = client.post(f"/api/v1/datasets/{ds['id']}/storage", json={"estimated_bytes": 9 * GIB},
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 409


def test_a_first_limit_is_refused_while_a_delivery_writes_into_an_unlimited_bucket(client, tmp_db) -> None:
    """A first "reservation" on a bucket with NO limit is a reduction, not a raise: set while a
    delivery is filling it, it could land below what the bucket already holds and stop it."""
    from gazzali.platform_push import build_desired_state

    s = _scaffold(client, tmp_db)
    ds = _pi_approved_without_estimate(client, s)
    client.post(f"/api/v1/datasets/{ds['id']}/admin-approve", json={"retention_until": _future(730)},
                headers=_auth(s["admin_token"]))
    client.post(f"/api/v1/datasets/{ds['id']}/transition", json={"status": "delivering"},
                headers=_auth(s["admin_token"]))
    r = client.post(f"/api/v1/datasets/{ds['id']}/storage", json={"estimated_bytes": GIB},
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 409, r.text
    assert "before delivery starts" in r.text
    assert build_desired_state(tmp_db, ds["id"])["dataset"]["quota_bytes"] == 0, "still no limit"


def test_a_first_limit_is_accepted_before_delivery(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _pi_approved_without_estimate(client, s)
    client.post(f"/api/v1/datasets/{ds['id']}/admin-approve", json={"retention_until": _future(730)},
                headers=_auth(s["admin_token"]))
    r = client.post(f"/api/v1/datasets/{ds['id']}/storage", json={"estimated_bytes": GIB},
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 200, r.text


def test_the_raise_is_one_conditional_write_so_a_lower_concurrent_raise_cannot_land(tmp_db) -> None:
    """Two admins read the same reservation; the higher raise lands first. The lower one must not
    then overwrite it — the condition, not the route's earlier check, is what decides."""
    from gazzali.auth import hash_password
    from gazzali.crud.datasets import (
        create_dataset,
        get_dataset,
        raise_estimated_bytes,
        update_dataset,
    )
    from gazzali.crud.labs import create_lab
    from gazzali.crud.users import create_user

    user = create_user(tmp_db, username="u", password_hash=hash_password("p"))
    lab = create_lab(tmp_db, name="L")
    ds = create_dataset(tmp_db, name="d", purpose="p", lab_id=lab.id, requested_by=user.id,
                        accession_list=["A1"], estimated_bytes=GIB)
    update_dataset(tmp_db, ds.id, status="approved")
    assert raise_estimated_bytes(tmp_db, ds.id, 4 * GIB) is True
    assert raise_estimated_bytes(tmp_db, ds.id, 2 * GIB) is False
    assert get_dataset(tmp_db, ds.id).estimated_bytes == 4 * GIB


def test_an_absurd_reservation_is_a_validation_error_not_a_crash(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)
    r = client.post(f"/api/v1/datasets/{ds['id']}/storage", json={"estimated_bytes": 10 ** 19},
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 422, r.text


def _approved_without_limit(client, s):
    ds = _pi_approved_without_estimate(client, s)
    r = client.post(f"/api/v1/datasets/{ds['id']}/admin-approve", json={"retention_until": _future(730)},
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 200, r.text
    return ds


def _with_catalogue(monkeypatch, usage):
    """platform-control configured, its catalogue answering `usage` (or raising it)."""
    import gazzali.api.routes.datasets as routes

    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_URL", "https://pc.invalid")
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_TOKEN", "t")
    monkeypatch.setattr("gazzali.platform_push.push_dataset", lambda *a, **k: True)
    monkeypatch.setattr(routes, "push_dataset", lambda *a, **k: True)

    def fake(_dataset_id):
        if isinstance(usage, Exception):
            raise usage
        return usage

    monkeypatch.setattr(routes, "bucket_usage", fake)


def test_a_first_limit_is_refused_on_a_bucket_that_already_holds_data(client, tmp_db, monkeypatch) -> None:
    """Medai never learns a delivery started (nothing sets 'delivering'), so a bucket with no limit
    that already holds objects may be filling right now: a first limit could land below it."""
    s = _scaffold(client, tmp_db)
    ds = _approved_without_limit(client, s)
    _with_catalogue(monkeypatch, (1200, 9 * GIB))
    r = client.post(f"/api/v1/datasets/{ds['id']}/storage", json={"estimated_bytes": GIB},
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 409, r.text
    assert "already holds 1200 objects" in r.text


def test_a_first_limit_is_refused_when_what_the_bucket_holds_cannot_be_read(client, tmp_db, monkeypatch) -> None:
    s = _scaffold(client, tmp_db)
    ds = _approved_without_limit(client, s)
    _with_catalogue(monkeypatch, OSError("gateway down"))
    r = client.post(f"/api/v1/datasets/{ds['id']}/storage", json={"estimated_bytes": GIB},
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 409, r.text
    assert "could not check" in r.text


@pytest.mark.parametrize("usage", [(0, 0), None])
def test_a_first_limit_is_accepted_on_an_empty_or_not_yet_created_bucket(client, tmp_db, monkeypatch, usage) -> None:
    s = _scaffold(client, tmp_db)
    ds = _approved_without_limit(client, s)
    _with_catalogue(monkeypatch, usage)
    r = client.post(f"/api/v1/datasets/{ds['id']}/storage", json={"estimated_bytes": GIB},
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 200, r.text


def test_raising_an_existing_limit_needs_no_look_at_the_bucket(client, tmp_db, monkeypatch) -> None:
    """A raise only ever grows the limit, so even an unreadable catalogue does not block it."""
    s = _scaffold(client, tmp_db)
    ds = _approved_dataset(client, s)                        # carries 500 MB from the request
    _with_catalogue(monkeypatch, OSError("gateway down"))
    r = client.post(f"/api/v1/datasets/{ds['id']}/storage", json={"estimated_bytes": 2 * GIB},
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 200, r.text


def test_bucket_usage_reads_the_dataset_s_own_entry(monkeypatch) -> None:
    from gazzali import platform_pull

    monkeypatch.setattr(platform_pull, "fetch_catalogue", lambda: [
        {"desired": {"dataset": {"id": "other"}}, "bucket": {"exists": True, "objects": 9, "bytes": 9}},
        {"desired": {"dataset": {"id": "mine"}}, "bucket": {"exists": True, "objects": 3, "bytes": 7}},
        {"desired": {"dataset": {"id": "fresh"}}, "bucket": {"exists": False}},
    ])
    assert platform_pull.bucket_usage("mine") == (3, 7)
    assert platform_pull.bucket_usage("fresh") is None
    assert platform_pull.bucket_usage("unknown") is None


def test_a_bucket_platform_control_could_not_read_is_unknown_not_empty(monkeypatch) -> None:
    """platform-control reports a failed bucket lookup as `exists: false` plus an entry-level
    `bucket_error` — which must refuse a first limit, never pass for "not created yet"."""
    from gazzali import platform_pull

    monkeypatch.setattr(platform_pull, "fetch_catalogue", lambda: [
        {"desired": {"dataset": {"id": "blip"}}, "bucket": {"name": "ds-blip", "exists": False},
         "bucket_error": "garage admin: context deadline exceeded"},
    ])
    with pytest.raises(RuntimeError, match="could not read the bucket"):
        platform_pull.bucket_usage("blip")


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
    # Delivery and sharing are independent from here: both are pending at once.
    assert _steps(client, s)[0]["waiting_on"] == "Delivery from PACS · Lab PI (share with the project)"

    # Sharing with the requesting project is offered to the PI, then activated by the admin.
    (item,) = _inbox(client, s["pi_token"])
    assert item["action"] == "propose-grant" and item["project_id"] == pid
    grant = client.post(f"/api/v1/datasets/{ds['id']}/grants", json={"project_id": pid},
                        headers=_auth(s["pi_token"])).json()
    assert _steps(client, s)[0]["waiting_on"] == "Delivery from PACS · Platform admin (activate access)"
    (item,) = [i for i in _inbox(client, s["admin_token"]) if i["action"] == "approve-grant"]
    assert item["grant_id"] == grant["id"]
    client.post(f"/api/v1/datasets/{ds['id']}/grants/{grant['id']}/approve", headers=_auth(s["admin_token"]))
    req = _steps(client, s)[0]
    assert _current(req) == "delivery" and req["waiting_on"] == "Delivery from PACS"

    # The cluster reports the delivery started (platform_pull records it): the bar says so.
    from gazzali.crud.datasets import update_dataset

    update_dataset(tmp_db, ds["id"], status="delivering")
    req = _steps(client, s)[0]
    assert _current(req) == "delivery"
    assert req["waiting_on"] == "Delivery in progress (PACS → cohort)"


def _states(req):
    return {st["key"]: st["state"] for st in req["steps"]}


def _approve_and_seal(client, s, ds_id):
    client.post(f"/api/v1/datasets/{ds_id}/pi-approve", headers=_auth(s["pi_token"]))
    r = client.post(f"/api/v1/datasets/{ds_id}/admin-approve",
                    json={"retention_until": _future(700)}, headers=_auth(s["admin_token"]))
    assert r.status_code == 200, r.text
    for body in ({"status": "delivering"}, {"status": "sealed", "content_root_sha256": "a" * 64}):
        r = client.post(f"/api/v1/datasets/{ds_id}/transition", json=body, headers=_auth(s["admin_token"]))
        assert r.status_code == 200, r.text


def test_a_sealed_dataset_shows_delivery_done_while_sharing_is_still_pending(client, tmp_db) -> None:
    """Delivery does not wait for a grant, so the tracker must not claim it does:
    a cohort that is delivered but not yet shared shows Delivery done and names the
    PI as the one step left."""
    s = _scaffold(client, tmp_db)
    ds = _draft(client, s, project_id=s["project"]["id"]).json()
    _approve_and_seal(client, s, ds["id"])
    (req,) = _steps(client, s)
    states = _states(req)
    assert states["delivery"] == "done"
    assert states["access"] == "current"
    assert states["ready"] == "todo"
    assert req["waiting_on"] == "Lab PI (share with the project)"


def test_a_sealed_and_shared_dataset_is_ready_with_nobody_to_wait_on(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    pid = s["project"]["id"]
    ds = _draft(client, s, project_id=pid).json()
    _approve_and_seal(client, s, ds["id"])
    grant = client.post(f"/api/v1/datasets/{ds['id']}/grants", json={"project_id": pid},
                        headers=_auth(s["pi_token"])).json()
    client.post(f"/api/v1/datasets/{ds['id']}/grants/{grant['id']}/approve", headers=_auth(s["admin_token"]))
    (req,) = _steps(client, s)
    assert set(_states(req).values()) == {"done"}
    assert req["waiting_on"] is None


def test_the_share_card_knows_whether_the_dataset_can_be_annotated(client, tmp_db) -> None:
    """The share card offers CVAT only when the server would accept it: an annotate
    grant on a dataset approved without viewable images is refused (409)."""
    s = _scaffold(client, tmp_db)
    pid = s["project"]["id"]
    for renders in (True, False):
        ds = _draft(client, s, project_id=pid, name=f"cohort renders={renders}", renders=renders).json()
        client.post(f"/api/v1/datasets/{ds['id']}/pi-approve", headers=_auth(s["pi_token"]))
        r = client.post(f"/api/v1/datasets/{ds['id']}/admin-approve",
                        json={"retention_until": _future(700)}, headers=_auth(s["admin_token"]))
        assert r.status_code == 200, r.text
    items = {i["dataset_name"]: i for i in _inbox(client, s["pi_token"]) if i["action"] == "propose-grant"}
    assert items["cohort renders=True"]["renders"] is True
    assert items["cohort renders=False"]["renders"] is False


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


# ── Filing from a saved Curator selection (the hand-off) ──────────────────────


def _req(s, **over):
    body = {"name": "DX ayak bilek 2019", "purpose": "fracture study", "lab_id": s["lab"]["id"],
            "irb_ids": [s["irb"]["id"]], "project_id": s["project"]["id"], "renders": False}
    body.update(over)
    return body


def test_a_researcher_files_their_own_request_from_a_saved_selection(client, tmp_db) -> None:
    """No administrator on the project, no list copied: the requester's own selection, fetched
    server to server — and the researcher sees how many studies, never which accession numbers."""
    s = _scaffold(client, tmp_db)
    sel = _saved_selection(["ACC1", "ACC2", "ACC3"], instances=30)
    r = client.post("/api/v1/datasets", json=_req(s, curator_selection_id=sel),
                    headers=_auth(s["pi_token"]))
    assert r.status_code == 201, r.text
    ds = r.json()
    assert ds["accession_count"] == 3
    assert ds["accession_list"] == []
    assert ds["requested_by"] == s["pi"].id
    # Curator was told the very id the dataset was created under, for this person's own address
    assert FAKE_CURATOR["submitted"] == [(sel, "pi_user@test.local", ds["id"])]
    # the platform admin (delivery, audits) does see the keys
    admin_view = client.get(f"/api/v1/datasets/{ds['id']}", headers=_auth(s["admin_token"])).json()
    assert admin_view["accession_list"] == ["ACC1", "ACC2", "ACC3"]
    member_view = client.get(f"/api/v1/datasets?lab_id={s['lab']['id']}", headers=_auth(s["ms_token"])).json()
    assert all(d["accession_list"] == [] for d in member_view), "a lab member never sees the keys"


def test_the_storage_estimate_comes_from_curators_measured_rate(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    sel = _saved_selection(["ACC1"], instances=100, rate=1_000_000, render_rate=200_000)
    r = client.post("/api/v1/datasets", json=_req(s, curator_selection_id=sel, renders=True),
                    headers=_auth(s["pi_token"]))
    # 100 images x (1 MB DICOM + 0.2 MB render), plus 25% margin
    assert r.json()["estimated_bytes"] == 150_000_000
    sel2 = _saved_selection(["ACC2"], instances=100, rate=1_000_000, render_rate=200_000)
    r2 = client.post("/api/v1/datasets", json=_req(s, curator_selection_id=sel2, renders=False),
                     headers=_auth(s["pi_token"]))
    assert r2.json()["estimated_bytes"] == 125_000_000, "no renders asked, none priced"


def test_only_a_platform_admin_may_file_by_typed_list(client, tmp_db) -> None:
    s = _scaffold(client, tmp_db)
    r = client.post("/api/v1/datasets", json=_req(s, accession_list=["A1"], project_id=None),
                    headers=_auth(s["pi_token"]))
    assert r.status_code == 400
    assert "saved Curator selections" in r.text
    r = client.post("/api/v1/datasets", json=_req(s, accession_list=["A1"], project_id=None),
                    headers=_auth(s["admin_token"]))
    assert r.status_code == 201, r.text
    sel = _saved_selection(["A2"])
    r = client.post("/api/v1/datasets", json=_req(s, accession_list=["A1"], curator_selection_id=sel),
                    headers=_auth(s["pi_token"]))
    assert r.status_code == 400
    assert "not both" in r.text


def _dataset_count(client, s) -> int:
    return len(client.get("/api/v1/datasets", headers=_auth(s["admin_token"])).json())


@pytest.mark.parametrize("case", ["already-requested", "not-yours", "curator-down"])
def test_a_refused_hand_off_files_nothing(client, tmp_db, monkeypatch, case) -> None:
    from gazzali import curator_bridge

    s = _scaffold(client, tmp_db)
    before = _dataset_count(client, s)
    sel = _saved_selection(["ACC1"])
    if case == "already-requested":
        FAKE_CURATOR["selections"][sel]["submitted"] = "f" * 32
        want = 409
    elif case == "not-yours":
        FAKE_CURATOR["selections"][sel]["owner"] = "somebody@else.org"
        want = 404
    else:
        def down(*_a, **_k):
            raise curator_bridge.CuratorUnavailable("gateway down")
        monkeypatch.setattr(curator_bridge, "submit_selection", down)
        want = 503
    r = client.post("/api/v1/datasets", json=_req(s, curator_selection_id=sel),
                    headers=_auth(s["pi_token"]))
    assert r.status_code == want, r.text
    assert _dataset_count(client, s) == before


def test_project_access_is_checked_before_curator_is_asked(client, tmp_db) -> None:
    """A refusal Medai can decide itself must never leave the selection marked in Curator."""
    s = _scaffold(client, tmp_db)
    sel = _saved_selection(["ACC1"])
    r = client.post("/api/v1/datasets", json=_req(s, curator_selection_id=sel),
                    headers=_auth(s["ms_token"]))           # lab member, not on the project
    assert r.status_code == 403, r.text
    assert FAKE_CURATOR["submitted"] == []


def test_a_failed_create_undoes_the_mark_in_curator(client, tmp_db, monkeypatch) -> None:
    import gazzali.api.routes.datasets as routes

    s = _scaffold(client, tmp_db)
    sel = _saved_selection(["ACC1"])

    def broken(*_a, **_k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(routes, "create_dataset", broken)
    with pytest.raises(RuntimeError):
        client.post("/api/v1/datasets", json=_req(s, curator_selection_id=sel),
                    headers=_auth(s["pi_token"]))
    assert len(FAKE_CURATOR["retracted"]) == 1
    assert FAKE_CURATOR["selections"][sel]["submitted"] is None


def test_without_the_curator_link_or_an_email_nothing_is_filed(client, tmp_db, monkeypatch) -> None:
    from gazzali import curator_bridge
    from gazzali.db import get_db

    s = _scaffold(client, tmp_db)
    sel = _saved_selection(["ACC1"])
    with get_db(tmp_db) as conn:
        conn.execute("UPDATE users SET email = NULL WHERE id = ?", (s["pi"].id,))
    r = client.post("/api/v1/datasets", json=_req(s, curator_selection_id=sel),
                    headers=_auth(s["pi_token"]))
    assert r.status_code == 409
    assert "no e-mail" in r.text
    monkeypatch.setattr(curator_bridge, "configured", lambda: False)
    r = client.post("/api/v1/datasets", json=_req(s, curator_selection_id=sel),
                    headers=_auth(s["pi_token"]))
    assert r.status_code == 503
    assert FAKE_CURATOR["submitted"] == []


def test_my_curator_selections_passes_counts_and_never_a_key(client, tmp_db, monkeypatch) -> None:
    from gazzali import curator_bridge

    s = _scaffold(client, tmp_db)
    asked = []

    def listing(email):
        asked.append(email)
        return {"selections": [{
            "id": "sel_" + "a" * 32, "name": "DX ayak bilek 2019", "created_at": "2026-10-17",
            "expires_at": "2026-11-16", "studies": 12, "status": "pending",
            "accessions": ["SHOULD-NOT-PASS"], "query": {"patient_name": "SHOULD-NOT-PASS"},
        }], "bytes_per_object": 0, "rate_source": "none"}

    monkeypatch.setattr(curator_bridge, "list_selections", listing)
    r = client.get("/api/v1/curator/selections", headers=_auth(s["ms_token"]))
    assert r.status_code == 200, r.text
    assert asked == ["ms_student@test.local"], "only the signed-in person's own selections"
    assert r.json()["selections"][0]["studies"] == 12
    assert "SHOULD-NOT-PASS" not in r.text
    monkeypatch.setattr(curator_bridge, "configured", lambda: False)
    assert client.get("/api/v1/curator/selections", headers=_auth(s["ms_token"])).status_code == 404


def test_a_timed_out_submit_is_retracted_and_files_nothing(client, tmp_db, monkeypatch) -> None:
    """Curator may have committed and only its answer was lost: Medai undoes it by exact id."""
    from gazzali import curator_bridge

    s = _scaffold(client, tmp_db)
    sel = _saved_selection(["ACC1"])
    real_submit = curator_bridge.submit_selection

    def commits_then_times_out(selection_id, email, dataset_id):
        real_submit(selection_id, email, dataset_id)
        raise curator_bridge.CuratorUnavailable("read timed out")

    monkeypatch.setattr(curator_bridge, "submit_selection", commits_then_times_out)
    r = client.post("/api/v1/datasets", json=_req(s, curator_selection_id=sel),
                    headers=_auth(s["pi_token"]))
    assert r.status_code == 503
    assert FAKE_CURATOR["selections"][sel]["submitted"] is None, "the lost hand-off was undone"


def test_opening_the_dialog_releases_an_orphaned_mark_but_never_a_fresh_or_real_one(client, tmp_db,
                                                                                 monkeypatch) -> None:
    """A selection stuck as 'already requested' with no dataset behind it is released for its owner;
    one just submitted (its dataset may be mid-creation) and one with a real dataset are left alone."""
    from datetime import UTC, datetime, timedelta

    from gazzali import curator_bridge

    s = _scaffold(client, tmp_db)
    real = client.post("/api/v1/datasets", json=_req(s, curator_selection_id=_saved_selection(["A"])),
                       headers=_auth(s["pi_token"])).json()
    old = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    fresh = datetime.now(UTC).isoformat()
    rows = [
        {"id": "sel_" + "1" * 32, "status": "submitted", "medai_dataset_id": "e" * 32, "submitted_at": old},
        {"id": "sel_" + "2" * 32, "status": "submitted", "medai_dataset_id": "f" * 32, "submitted_at": fresh},
        {"id": "sel_" + "3" * 32, "status": "submitted", "medai_dataset_id": real["id"], "submitted_at": old},
    ]
    listing = {"selections": [{"name": "x", "created_at": old, "expires_at": old, "studies": 1, **r} for r in rows]}
    monkeypatch.setattr(curator_bridge, "list_selections", lambda email: listing)
    retracted = []
    monkeypatch.setattr(curator_bridge, "retract_selection",
                        lambda sel, email, ds: retracted.append((sel, email, ds)) or True)
    r = client.get("/api/v1/curator/selections", headers=_auth(s["pi_token"]))
    assert r.status_code == 200, r.text
    assert retracted == [("sel_" + "1" * 32, "pi_user@test.local", "e" * 32)]
    by_id = {x["id"]: x for x in r.json()["selections"]}
    assert by_id["sel_" + "1" * 32]["status"] == "pending"
    assert by_id["sel_" + "2" * 32]["status"] == "submitted"
    assert by_id["sel_" + "3" * 32]["status"] == "submitted"
