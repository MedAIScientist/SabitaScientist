"""Tests for the grant plan: budget lines, milestones/reports and the team.

Also covers the status vocabulary the API accepts (it once drifted from the
CHECK constraint in db.py, making 'under_review' and 'active' unusable) and the
aggregate stats dashboard.
"""

from __future__ import annotations

import sqlite3
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
        role="professor",  # these users create and lead labs; only professors may
    )
    token = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    ).json()["token"]
    return user, token


def _lab_with_pi(client, tmp_db, name="Grant Lab"):
    pi, pi_token = _make_user(client, tmp_db, "grant_pi")
    resp = client.post("/api/v1/labs", json={"name": name}, headers=_auth(pi_token))
    assert resp.status_code == 201
    return resp.json(), pi, pi_token


def _grant(client, token, **body):
    payload = {"title": "R01", "funder": "NIH", "amount_awarded": 50000, **body}
    resp = client.post("/api/v1/grants", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_budget(client, token, gid, **body):
    payload = {"category": "personnel", "planned_amount": 1000, **body}
    return client.post(
        f"/api/v1/grants/{gid}/budget", json=payload, headers=_auth(token)
    )


def _add_milestone(client, token, gid, **body):
    payload = {"title": "First report", **body}
    return client.post(
        f"/api/v1/grants/{gid}/milestones", json=payload, headers=_auth(token)
    )


# ── Status vocabulary ─────────────────────────────────────────────────────────


def test_update_accepts_every_status_in_the_db_constraint(client, tmp_db) -> None:
    """'under_review' and 'active' used to be rejected with a 422."""
    _pi, token = _make_user(client, tmp_db, "status_pi")
    grant = _grant(client, token)
    for status in (
        "draft",
        "submitted",
        "under_review",
        "awarded",
        "rejected",
        "active",
        "closed",
    ):
        resp = client.put(
            f"/api/v1/grants/{grant['id']}",
            json={"status": status},
            headers=_auth(token),
        )
        assert resp.status_code == 200, f"{status}: {resp.text}"
        assert resp.json()["status"] == status


def test_create_accepts_active_status(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "create_active_pi")
    resp = client.post(
        "/api/v1/grants",
        json={"title": "Running", "funder": "TUBITAK", "status": "active"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "active"


def test_unknown_status_is_still_rejected(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "bogus_status_pi")
    grant = _grant(client, token)
    resp = client.put(
        f"/api/v1/grants/{grant['id']}",
        json={"status": "nonsense"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


# ── Stats dashboard ───────────────────────────────────────────────────────────


def test_stats_aggregates_counts_totals_and_success_rate(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "stats_pi")
    # amounts are explicit here: _grant() defaults amount_awarded to 50000
    _grant(client, token, status="awarded", amount_awarded=100, amount_requested=100)
    _grant(client, token, status="active", amount_awarded=200, amount_requested=200)
    _grant(client, token, status="rejected", amount_awarded=0, amount_requested=50)
    _grant(
        client,
        token,
        status="draft",
        amount_awarded=0,
        amount_requested=10,
        currency="EUR",
    )

    resp = client.get("/api/v1/grants/stats", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["total"] == 4
    assert body["by_status"]["awarded"] == 1
    assert body["by_status"]["active"] == 1
    # draft is still in flight, so it is not counted as decided
    assert body["decided"] == 3
    assert body["won"] == 2
    assert body["success_rate"] == round(2 / 3, 4)

    by_currency = {t["currency"]: t for t in body["totals_by_currency"]}
    assert by_currency["TRY"]["awarded"] == 300
    assert by_currency["TRY"]["requested"] == 350
    assert by_currency["TRY"]["count"] == 3
    assert by_currency["EUR"]["count"] == 1


def test_stats_is_empty_for_a_caller_who_sees_nothing(client, tmp_db) -> None:
    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    _grant(client, pi_token, lab_id=lab["id"], amount_awarded=999)
    _outsider, outsider_token = _make_user(client, tmp_db, "stats_outsider")

    body = client.get("/api/v1/grants/stats", headers=_auth(outsider_token)).json()
    assert body["total"] == 0
    assert body["totals_by_currency"] == []
    assert body["success_rate"] is None


def test_stats_counts_overdue_milestones_and_open_reports(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "plan_stats_pi")
    grant = _grant(client, token)
    gid = grant["id"]
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    _add_milestone(client, token, gid, title="Late", due_date=yesterday)
    _add_milestone(client, token, gid, title="Report", kind="report")
    done = _add_milestone(client, token, gid, title="Done", due_date=yesterday)
    client.put(
        f"/api/v1/grants/{gid}/milestones/{done.json()['id']}",
        json={"completed": True},
        headers=_auth(token),
    )
    _add_budget(client, token, gid, planned_amount=500, spent_amount=125)

    body = client.get("/api/v1/grants/stats", headers=_auth(token)).json()
    assert body["overdue_milestones"] == 1  # the completed one no longer counts
    assert body["open_reports"] == 1
    assert body["budget_planned"] == 500
    assert body["budget_spent"] == 125


def test_stats_counts_grants_ending_soon(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "ending_pi")
    soon = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()
    far = (datetime.now(UTC).date() + timedelta(days=800)).isoformat()
    _grant(client, token, status="active", end_date=soon)
    _grant(client, token, status="active", end_date=far)
    # a draft ending soon is not "ending soon" — it never started
    _grant(client, token, status="draft", end_date=soon)

    body = client.get("/api/v1/grants/stats", headers=_auth(token)).json()
    assert body["ending_soon"] == 1


# ── Search and sort ───────────────────────────────────────────────────────────


def test_search_matches_title_and_funder(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "search_pi")
    _grant(client, token, title="Alzheimer biomarkers", funder="TUBITAK")
    _grant(client, token, title="Retina segmentation", funder="NIH")

    by_title = client.get("/api/v1/grants?q=alzheimer", headers=_auth(token)).json()
    assert [g["title"] for g in by_title] == ["Alzheimer biomarkers"]

    by_funder = client.get("/api/v1/grants?q=nih", headers=_auth(token)).json()
    assert [g["title"] for g in by_funder] == ["Retina segmentation"]


def test_sort_by_awarded_amount(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "sort_pi")
    _grant(client, token, title="Small", amount_awarded=10)
    _grant(client, token, title="Large", amount_awarded=999)

    desc = client.get(
        "/api/v1/grants?sort=-amount_awarded", headers=_auth(token)
    ).json()
    assert [g["title"] for g in desc][:2] == ["Large", "Small"]


# ── Budget lines ──────────────────────────────────────────────────────────────


def test_budget_line_roundtrip(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "budget_pi")
    gid = _grant(client, token)["id"]

    created = _add_budget(
        client,
        token,
        gid,
        category="equipment",
        description="Sequencer",
        planned_amount=4000,
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    assert created.json()["spent_amount"] == 0

    listed = client.get(f"/api/v1/grants/{gid}/budget", headers=_auth(token)).json()
    assert [i["id"] for i in listed] == [item_id]

    updated = client.put(
        f"/api/v1/grants/{gid}/budget/{item_id}",
        json={"spent_amount": 2500},
        headers=_auth(token),
    )
    assert updated.status_code == 200
    assert updated.json()["spent_amount"] == 2500
    assert updated.json()["planned_amount"] == 4000  # untouched

    assert (
        client.delete(
            f"/api/v1/grants/{gid}/budget/{item_id}", headers=_auth(token)
        ).status_code
        == 204
    )
    assert client.get(f"/api/v1/grants/{gid}/budget", headers=_auth(token)).json() == []


def test_budget_rejects_a_negative_amount(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "neg_pi")
    gid = _grant(client, token)["id"]
    assert _add_budget(client, token, gid, planned_amount=-5).status_code == 422


def test_budget_item_of_another_grant_is_404(client, tmp_db) -> None:
    """A line id must not be reachable through a different grant's URL."""
    _pi, token = _make_user(client, tmp_db, "xgrant_pi")
    gid_a = _grant(client, token, title="A")["id"]
    gid_b = _grant(client, token, title="B")["id"]
    item_id = _add_budget(client, token, gid_a).json()["id"]

    assert (
        client.put(
            f"/api/v1/grants/{gid_b}/budget/{item_id}",
            json={"spent_amount": 1},
            headers=_auth(token),
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/grants/{gid_b}/budget/{item_id}", headers=_auth(token)
        ).status_code
        == 404
    )
    # still there, untouched
    assert (
        len(client.get(f"/api/v1/grants/{gid_a}/budget", headers=_auth(token)).json())
        == 1
    )


# ── Milestones ────────────────────────────────────────────────────────────────


def test_milestone_completed_toggle(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "milestone_pi")
    gid = _grant(client, token)["id"]
    mid = _add_milestone(client, token, gid, kind="report").json()["id"]

    done = client.put(
        f"/api/v1/grants/{gid}/milestones/{mid}",
        json={"completed": True},
        headers=_auth(token),
    )
    assert done.status_code == 200
    assert done.json()["completed_at"] is not None

    reopened = client.put(
        f"/api/v1/grants/{gid}/milestones/{mid}",
        json={"completed": False},
        headers=_auth(token),
    )
    assert reopened.status_code == 200
    assert reopened.json()["completed_at"] is None


def test_milestone_partial_update_leaves_other_fields_alone(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "partial_pi")
    gid = _grant(client, token)["id"]
    mid = _add_milestone(client, token, gid, title="Keep me", notes="original").json()[
        "id"
    ]

    resp = client.put(
        f"/api/v1/grants/{gid}/milestones/{mid}",
        json={"notes": "changed"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Keep me"
    assert resp.json()["notes"] == "changed"


def test_milestone_unknown_owner_is_rejected(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "owner_pi")
    gid = _grant(client, token)["id"]
    assert (
        _add_milestone(client, token, gid, owner_id="does-not-exist").status_code == 400
    )


def test_milestone_of_another_grant_is_404(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "xmilestone_pi")
    gid_a = _grant(client, token, title="A")["id"]
    gid_b = _grant(client, token, title="B")["id"]
    mid = _add_milestone(client, token, gid_a).json()["id"]
    assert (
        client.delete(
            f"/api/v1/grants/{gid_b}/milestones/{mid}", headers=_auth(token)
        ).status_code
        == 404
    )


def test_milestones_are_ordered_by_due_date_with_undated_last(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "order_pi")
    gid = _grant(client, token)["id"]
    today = datetime.now(UTC).date()
    _add_milestone(client, token, gid, title="No date")
    _add_milestone(
        client,
        token,
        gid,
        title="Later",
        due_date=(today + timedelta(days=9)).isoformat(),
    )
    _add_milestone(
        client,
        token,
        gid,
        title="Sooner",
        due_date=(today + timedelta(days=2)).isoformat(),
    )

    titles = [
        m["title"]
        for m in client.get(
            f"/api/v1/grants/{gid}/milestones", headers=_auth(token)
        ).json()
    ]
    assert titles == ["Sooner", "Later", "No date"]


# ── Team ──────────────────────────────────────────────────────────────────────


def test_team_add_list_update_remove(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "team_pi")
    gid = _grant(client, token)["id"]
    member, _member_token = _make_user(client, tmp_db, "researcher_one")

    created = client.post(
        f"/api/v1/grants/{gid}/members",
        json={"user_id": member.id, "role": "co_pi", "share_percent": 25},
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    assert created.json()["username"] == "researcher_one"
    assert created.json()["role"] == "co_pi"
    row_id = created.json()["id"]

    listed = client.get(f"/api/v1/grants/{gid}/members", headers=_auth(token)).json()
    assert [m["id"] for m in listed] == [row_id]

    updated = client.put(
        f"/api/v1/grants/{gid}/members/{row_id}",
        json={"role": "advisor"},
        headers=_auth(token),
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "advisor"

    assert (
        client.delete(
            f"/api/v1/grants/{gid}/members/{row_id}", headers=_auth(token)
        ).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/grants/{gid}/members", headers=_auth(token)).json() == []
    )


def test_adding_the_same_member_twice_is_409(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "dup_pi")
    gid = _grant(client, token)["id"]
    member, _t = _make_user(client, tmp_db, "dup_member")
    body = {"user_id": member.id, "role": "researcher"}

    assert (
        client.post(
            f"/api/v1/grants/{gid}/members", json=body, headers=_auth(token)
        ).status_code
        == 201
    )
    again = client.post(
        f"/api/v1/grants/{gid}/members", json=body, headers=_auth(token)
    )
    assert again.status_code == 409


def test_adding_an_unknown_user_is_rejected(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "ghost_pi")
    gid = _grant(client, token)["id"]
    resp = client.post(
        f"/api/v1/grants/{gid}/members",
        json={"user_id": "nobody", "role": "researcher"},
        headers=_auth(token),
    )
    assert resp.status_code == 400


def test_share_percent_above_100_is_rejected(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "share_pi")
    gid = _grant(client, token)["id"]
    member, _t = _make_user(client, tmp_db, "share_member")
    resp = client.post(
        f"/api/v1/grants/{gid}/members",
        json={"user_id": member.id, "share_percent": 150},
        headers=_auth(token),
    )
    assert resp.status_code == 422


# ── Permissions and cascade ───────────────────────────────────────────────────


def test_outsider_sees_404_on_every_subresource(client, tmp_db) -> None:
    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    gid = _grant(client, pi_token, lab_id=lab["id"])["id"]
    _add_budget(client, pi_token, gid)
    _add_milestone(client, pi_token, gid)
    _outsider, outsider_token = _make_user(client, tmp_db, "plan_outsider")

    for path in ("budget", "milestones", "members"):
        resp = client.get(f"/api/v1/grants/{gid}/{path}", headers=_auth(outsider_token))
        assert resp.status_code == 404, f"{path}: {resp.status_code}"


def test_reader_role_can_read_but_not_write_the_plan(client, tmp_db) -> None:
    from EvoScientist.pm.crud.labs import add_member

    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    gid = _grant(client, pi_token, lab_id=lab["id"])["id"]
    _add_budget(client, pi_token, gid)

    student, student_token = _make_user(client, tmp_db, "plan_student")
    add_member(tmp_db, lab["id"], student.id, "ms")

    assert (
        client.get(
            f"/api/v1/grants/{gid}/budget", headers=_auth(student_token)
        ).status_code
        == 200
    )
    assert _add_budget(client, student_token, gid).status_code == 403
    assert _add_milestone(client, student_token, gid).status_code == 403
    assert (
        client.post(
            f"/api/v1/grants/{gid}/members",
            json={"user_id": student.id},
            headers=_auth(student_token),
        ).status_code
        == 403
    )


def test_can_manage_flag_matches_write_access(client, tmp_db) -> None:
    """The UI hides edit affordances off this flag, so it must track real access."""
    from EvoScientist.pm.crud.labs import add_member

    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    gid = _grant(client, pi_token, lab_id=lab["id"])["id"]

    mine = client.get(f"/api/v1/grants/{gid}", headers=_auth(pi_token)).json()
    assert mine["can_manage"] is True
    assert (
        client.get("/api/v1/grants", headers=_auth(pi_token)).json()[0]["can_manage"]
        is True
    )

    student, student_token = _make_user(client, tmp_db, "flag_student")
    add_member(tmp_db, lab["id"], student.id, "ms")
    readable = client.get(f"/api/v1/grants/{gid}", headers=_auth(student_token)).json()
    assert readable["can_manage"] is False


def test_deleting_a_grant_cascades_to_its_plan_rows(client, tmp_db) -> None:
    _pi, token = _make_user(client, tmp_db, "cascade_pi")
    gid = _grant(client, token)["id"]
    member, _t = _make_user(client, tmp_db, "cascade_member")
    _add_budget(client, token, gid)
    _add_milestone(client, token, gid)
    client.post(
        f"/api/v1/grants/{gid}/members",
        json={"user_id": member.id},
        headers=_auth(token),
    )

    assert (
        client.delete(f"/api/v1/grants/{gid}", headers=_auth(token)).status_code == 204
    )

    with sqlite3.connect(tmp_db) as conn:
        for table in ("grant_budget_items", "grant_milestones", "grant_members"):
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE grant_id=?", (gid,)
            ).fetchone()[0]
            assert count == 0, f"{table} still has {count} row(s)"
