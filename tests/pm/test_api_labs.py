"""Tests for /labs routes, lab-role enforcement and /pi/stats scoping."""


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_user(client, tmp_db, username, password="pw", is_admin=False):
    """Create a user in the temp DB and return (user, token)."""
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


def _lab_with_pi(client, tmp_db, name="Imaging Lab"):
    """Create a non-admin PI plus a lab they created. Returns (lab, pi, pi_token)."""
    pi, pi_token = _make_user(client, tmp_db, "pi_user")
    resp = client.post("/api/v1/labs", json={"name": name}, headers=_auth(pi_token))
    assert resp.status_code == 201
    return resp.json(), pi, pi_token


# ── POST /labs keeps labs.pi_id and the lab_members 'pi' row in agreement ─────


def test_create_lab_sets_pi_id_and_pi_member(client, tmp_db) -> None:
    from gazzali.crud.labs import get_lab, get_member_role

    lab, pi, _pi_token = _lab_with_pi(client, tmp_db)
    assert lab["pi_id"] == pi.id
    assert any(m["user_id"] == pi.id and m["role"] == "pi" for m in lab["members"])
    # and the two records agree in the DB, not just in the response
    assert get_lab(tmp_db, lab["id"]).pi_id == pi.id
    assert get_member_role(tmp_db, lab["id"], pi.id) == "pi"


# ── The roster travels only to members; the size travels to everyone ──────────


def test_nonmember_get_lab_sees_size_but_no_roster(client, tmp_db) -> None:
    """The live hole: every lab's membership was readable platform-wide."""
    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    student, _student_token = _make_user(client, tmp_db, "student")
    client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": student.id, "role": "ms"},
        headers=_auth(pi_token),
    )

    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")
    resp = client.get(f"/api/v1/labs/{lab['id']}", headers=_auth(outsider_token))
    assert resp.status_code == 200
    data = resp.json()
    # the lab itself is not secret, and its size is not either
    assert data["name"] == lab["name"]
    assert data["member_count"] == 2
    # but who is in it is: an empty list, never null — the live UI calls
    # .find()/.length/.map() on it unguarded
    assert data["members"] == []
    assert data["can_manage"] is False


def test_nonmember_list_labs_sees_size_but_no_roster(client, tmp_db) -> None:
    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")

    resp = client.get("/api/v1/labs", headers=_auth(outsider_token))
    assert resp.status_code == 200
    entry = next(entry for entry in resp.json() if entry["id"] == lab["id"])
    assert entry["members"] == []
    assert entry["member_count"] == 1
    assert entry["can_manage"] is False


def test_member_sees_the_roster(client, tmp_db) -> None:
    from gazzali.crud.labs import add_member

    lab, pi, _pi_token = _lab_with_pi(client, tmp_db)
    visitor, visitor_token = _make_user(client, tmp_db, "visitor_user")
    add_member(tmp_db, lab["id"], visitor.id, "visitor")

    detail = client.get(
        f"/api/v1/labs/{lab['id']}", headers=_auth(visitor_token)
    ).json()
    assert {m["user_id"] for m in detail["members"]} == {pi.id, visitor.id}
    assert detail["member_count"] == 2
    # a plain member reads the roster but still may not manage the lab
    assert detail["can_manage"] is False

    listing = client.get("/api/v1/labs", headers=_auth(visitor_token)).json()
    entry = next(entry for entry in listing if entry["id"] == lab["id"])
    assert {m["user_id"] for m in entry["members"]} == {pi.id, visitor.id}


def test_platform_admin_sees_the_roster_without_membership(
    client, tmp_db, admin_token
) -> None:
    from gazzali.crud.labs import get_member_role

    lab, pi, _pi_token = _lab_with_pi(client, tmp_db)
    admin_user_id = client.get("/api/v1/users/me", headers=_auth(admin_token)).json()[
        "id"
    ]
    assert get_member_role(tmp_db, lab["id"], admin_user_id) is None

    detail = client.get(f"/api/v1/labs/{lab['id']}", headers=_auth(admin_token)).json()
    assert [m["user_id"] for m in detail["members"]] == [pi.id]
    assert detail["member_count"] == 1
    assert detail["can_manage"] is True


def test_can_manage_matches_who_may_actually_write(client, tmp_db) -> None:
    """The flag the UI hides buttons on must agree with require_lab_role."""
    from gazzali.crud.labs import add_member

    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    assert client.get(f"/api/v1/labs/{lab['id']}", headers=_auth(pi_token)).json()[
        "can_manage"
    ]

    lab_admin, lab_admin_token = _make_user(client, tmp_db, "lab_admin")
    add_member(tmp_db, lab["id"], lab_admin.id, "admin")
    assert client.get(
        f"/api/v1/labs/{lab['id']}", headers=_auth(lab_admin_token)
    ).json()["can_manage"]

    postdoc, postdoc_token = _make_user(client, tmp_db, "postdoc_user")
    add_member(tmp_db, lab["id"], postdoc.id, "postdoc")
    assert (
        client.get(f"/api/v1/labs/{lab['id']}", headers=_auth(postdoc_token)).json()[
            "can_manage"
        ]
        is False
    )
    # and the route agrees with the flag it just published
    assert (
        client.put(
            f"/api/v1/labs/{lab['id']}",
            json={"name": "Renamed"},
            headers=_auth(postdoc_token),
        ).status_code
        == 403
    )


def test_member_count_tracks_the_roster(client, tmp_db) -> None:
    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    student, _student_token = _make_user(client, tmp_db, "student")

    added = client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": student.id, "role": "ms"},
        headers=_auth(pi_token),
    )
    assert added.status_code == 201
    assert (
        client.get(f"/api/v1/labs/{lab['id']}", headers=_auth(pi_token)).json()[
            "member_count"
        ]
        == 2
    )

    client.delete(
        f"/api/v1/labs/{lab['id']}/members/{student.id}", headers=_auth(pi_token)
    )
    assert (
        client.get(f"/api/v1/labs/{lab['id']}", headers=_auth(pi_token)).json()[
            "member_count"
        ]
        == 1
    )


# ── Non-members are refused on every write path ───────────────────────────────


def test_nonmember_cannot_add_member(client, tmp_db) -> None:
    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    outsider, outsider_token = _make_user(client, tmp_db, "outsider")

    resp = client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": outsider.id, "role": "phd"},
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "lab membership required (pi or admin)"


def test_nonmember_cannot_remove_member(client, tmp_db) -> None:
    lab, pi, _pi_token = _lab_with_pi(client, tmp_db)
    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")

    resp = client.delete(
        f"/api/v1/labs/{lab['id']}/members/{pi.id}", headers=_auth(outsider_token)
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "lab membership required (pi or admin)"


def test_nonmember_cannot_update_lab(client, tmp_db) -> None:
    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")

    resp = client.put(
        f"/api/v1/labs/{lab['id']}",
        json={"name": "Hijacked Lab"},
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "lab membership required (pi or admin)"


def test_nonmember_cannot_change_member_role(client, tmp_db) -> None:
    lab, pi, _pi_token = _lab_with_pi(client, tmp_db)
    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")

    resp = client.put(
        f"/api/v1/labs/{lab['id']}/members/{pi.id}",
        json={"role": "visitor"},
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "lab membership required (pi or admin)"


def test_nonmember_cannot_reassign_pi_id(client, tmp_db) -> None:
    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    outsider, outsider_token = _make_user(client, tmp_db, "outsider")

    resp = client.put(
        f"/api/v1/labs/{lab['id']}",
        json={"pi_id": outsider.id},
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403


# ── Members in ordinary roles are refused too, with their role named ──────────


def test_ms_member_cannot_add_member(client, tmp_db) -> None:
    """The live audit case: an 'ms' member inserting somebody else as 'pi'."""
    from gazzali.crud.labs import add_member

    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    student, student_token = _make_user(client, tmp_db, "student")
    victim, _victim_token = _make_user(client, tmp_db, "victim")
    add_member(tmp_db, lab["id"], student.id, "ms")

    resp = client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": victim.id, "role": "pi"},
        headers=_auth(student_token),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Role 'ms' not permitted here"


def test_postdoc_member_cannot_update_or_remove_or_change_role(client, tmp_db) -> None:
    from gazzali.crud.labs import add_member

    lab, pi, _pi_token = _lab_with_pi(client, tmp_db)
    postdoc, postdoc_token = _make_user(client, tmp_db, "postdoc_user")
    add_member(tmp_db, lab["id"], postdoc.id, "postdoc")

    update = client.put(
        f"/api/v1/labs/{lab['id']}",
        json={"name": "Renamed"},
        headers=_auth(postdoc_token),
    )
    assert update.status_code == 403
    assert update.json()["detail"] == "Role 'postdoc' not permitted here"

    remove = client.delete(
        f"/api/v1/labs/{lab['id']}/members/{pi.id}", headers=_auth(postdoc_token)
    )
    assert remove.status_code == 403
    assert remove.json()["detail"] == "Role 'postdoc' not permitted here"

    role_change = client.put(
        f"/api/v1/labs/{lab['id']}/members/{pi.id}",
        json={"role": "visitor"},
        headers=_auth(postdoc_token),
    )
    assert role_change.status_code == 403
    assert role_change.json()["detail"] == "Role 'postdoc' not permitted here"


def test_postdoc_member_cannot_reassign_pi_id(client, tmp_db) -> None:
    from gazzali.crud.labs import add_member, get_lab

    lab, pi, _pi_token = _lab_with_pi(client, tmp_db)
    postdoc, postdoc_token = _make_user(client, tmp_db, "postdoc_user")
    add_member(tmp_db, lab["id"], postdoc.id, "postdoc")

    resp = client.put(
        f"/api/v1/labs/{lab['id']}",
        json={"pi_id": postdoc.id},
        headers=_auth(postdoc_token),
    )
    assert resp.status_code == 403
    assert get_lab(tmp_db, lab["id"]).pi_id == pi.id


# ── The lab PI can do all four ────────────────────────────────────────────────


def test_pi_can_add_change_role_update_and_remove(client, tmp_db) -> None:
    from gazzali.crud.labs import get_member_role

    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    student, _student_token = _make_user(client, tmp_db, "student")

    add = client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": student.id, "role": "ms"},
        headers=_auth(pi_token),
    )
    assert add.status_code == 201
    assert add.json()["role"] == "ms"

    role_change = client.put(
        f"/api/v1/labs/{lab['id']}/members/{student.id}",
        json={"role": "phd"},
        headers=_auth(pi_token),
    )
    assert role_change.status_code == 200
    assert role_change.json()["role"] == "phd"
    assert get_member_role(tmp_db, lab["id"], student.id) == "phd"

    update = client.put(
        f"/api/v1/labs/{lab['id']}",
        json={"name": "Renamed Lab", "department": "Radiology"},
        headers=_auth(pi_token),
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Renamed Lab"
    assert update.json()["department"] == "Radiology"

    remove = client.delete(
        f"/api/v1/labs/{lab['id']}/members/{student.id}", headers=_auth(pi_token)
    )
    assert remove.status_code == 204
    assert get_member_role(tmp_db, lab["id"], student.id) is None


# ── The platform admin can do all four without being a member ────────────────


def test_platform_admin_can_manage_lab_without_membership(
    client, tmp_db, admin_token
) -> None:
    from gazzali.crud.labs import get_member_role

    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    admin_user_id = client.get("/api/v1/users/me", headers=_auth(admin_token)).json()[
        "id"
    ]
    assert get_member_role(tmp_db, lab["id"], admin_user_id) is None

    student, _student_token = _make_user(client, tmp_db, "student")

    add = client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": student.id, "role": "ms"},
        headers=_auth(admin_token),
    )
    assert add.status_code == 201

    role_change = client.put(
        f"/api/v1/labs/{lab['id']}/members/{student.id}",
        json={"role": "phd"},
        headers=_auth(admin_token),
    )
    assert role_change.status_code == 200

    update = client.put(
        f"/api/v1/labs/{lab['id']}",
        json={"name": "Admin Renamed"},
        headers=_auth(admin_token),
    )
    assert update.status_code == 200

    remove = client.delete(
        f"/api/v1/labs/{lab['id']}/members/{student.id}", headers=_auth(admin_token)
    )
    assert remove.status_code == 204


# ── Duplicate add is a conflict, not a 500 ────────────────────────────────────


def test_duplicate_add_member_returns_409(client, tmp_db) -> None:
    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    student, _student_token = _make_user(client, tmp_db, "student")

    first = client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": student.id, "role": "ms"},
        headers=_auth(pi_token),
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": student.id, "role": "phd"},
        headers=_auth(pi_token),
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "user is already a member of this lab"


# ── pi_id reassignment ────────────────────────────────────────────────────────


def test_lab_admin_member_cannot_reassign_pi_id(client, tmp_db) -> None:
    """A 'admin'-role lab member passes the role gate but is not the PI."""
    from gazzali.crud.labs import add_member, get_lab

    lab, pi, _pi_token = _lab_with_pi(client, tmp_db)
    lab_admin, lab_admin_token = _make_user(client, tmp_db, "lab_admin")
    add_member(tmp_db, lab["id"], lab_admin.id, "admin")

    # may rename the lab
    rename = client.put(
        f"/api/v1/labs/{lab['id']}",
        json={"name": "Renamed By Lab Admin"},
        headers=_auth(lab_admin_token),
    )
    assert rename.status_code == 200

    # but may not hand the lab to someone else
    handover = client.put(
        f"/api/v1/labs/{lab['id']}",
        json={"pi_id": lab_admin.id},
        headers=_auth(lab_admin_token),
    )
    assert handover.status_code == 403
    assert (
        handover.json()["detail"]
        == "only the lab PI or a platform admin can reassign pi_id"
    )
    assert get_lab(tmp_db, lab["id"]).pi_id == pi.id


def test_pi_id_target_must_be_lab_member(client, tmp_db) -> None:
    from gazzali.crud.labs import get_lab

    lab, pi, pi_token = _lab_with_pi(client, tmp_db)
    outsider, _outsider_token = _make_user(client, tmp_db, "outsider")

    resp = client.put(
        f"/api/v1/labs/{lab['id']}",
        json={"pi_id": outsider.id},
        headers=_auth(pi_token),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "new pi_id must already be a member of this lab"
    assert get_lab(tmp_db, lab["id"]).pi_id == pi.id


def test_pi_can_reassign_pi_id_to_member(client, tmp_db) -> None:
    from gazzali.crud.labs import get_lab

    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    successor, _successor_token = _make_user(client, tmp_db, "successor")
    client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": successor.id, "role": "pi"},
        headers=_auth(pi_token),
    )

    resp = client.put(
        f"/api/v1/labs/{lab['id']}",
        json={"pi_id": successor.id},
        headers=_auth(pi_token),
    )
    assert resp.status_code == 200
    assert resp.json()["pi_id"] == successor.id
    assert get_lab(tmp_db, lab["id"]).pi_id == successor.id


def test_platform_admin_can_reassign_pi_id(client, tmp_db, admin_token) -> None:
    from gazzali.crud.labs import add_member, get_lab

    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    successor, _successor_token = _make_user(client, tmp_db, "successor")
    add_member(tmp_db, lab["id"], successor.id, "postdoc")

    resp = client.put(
        f"/api/v1/labs/{lab['id']}",
        json={"pi_id": successor.id},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert get_lab(tmp_db, lab["id"]).pi_id == successor.id


def test_legacy_pi_with_null_pi_id_can_repair_it(client, tmp_db) -> None:
    """Production labs predate pi_id being set, so the 'pi' row is the PI proof."""
    from gazzali.crud.labs import get_lab
    from gazzali.db import get_db

    lab, pi, pi_token = _lab_with_pi(client, tmp_db)
    with get_db(tmp_db) as conn:
        conn.execute("UPDATE labs SET pi_id = NULL WHERE id = ?", (lab["id"],))
    assert get_lab(tmp_db, lab["id"]).pi_id is None

    resp = client.put(
        f"/api/v1/labs/{lab['id']}", json={"pi_id": pi.id}, headers=_auth(pi_token)
    )
    assert resp.status_code == 200
    assert get_lab(tmp_db, lab["id"]).pi_id == pi.id


# ── Role change: persistence, unknown member, invalid role ───────────────────


def test_change_role_of_unknown_member_returns_404(client, tmp_db) -> None:
    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    stranger, _stranger_token = _make_user(client, tmp_db, "stranger")

    resp = client.put(
        f"/api/v1/labs/{lab['id']}/members/{stranger.id}",
        json={"role": "phd"},
        headers=_auth(pi_token),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Lab member not found"


def test_change_role_rejects_invalid_role(client, tmp_db) -> None:
    from gazzali.crud.labs import get_member_role

    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    student, _student_token = _make_user(client, tmp_db, "student")
    client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": student.id, "role": "ms"},
        headers=_auth(pi_token),
    )

    resp = client.put(
        f"/api/v1/labs/{lab['id']}/members/{student.id}",
        json={"role": "supreme_leader"},
        headers=_auth(pi_token),
    )
    assert resp.status_code == 422
    assert get_member_role(tmp_db, lab["id"], student.id) == "ms"


# ── Lab wiki is members-only ─────────────────────────────────────────────────


def test_wiki_refuses_non_member_and_allows_member(client, tmp_db) -> None:
    from gazzali.crud.labs import add_member

    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    page = client.post(
        f"/api/v1/labs/{lab['id']}/wiki",
        json={"title": "Protocols", "content": "secret", "tags": []},
        headers=_auth(pi_token),
    )
    assert page.status_code == 201
    page_id = page.json()["id"]

    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")
    listing = client.get(
        f"/api/v1/labs/{lab['id']}/wiki", headers=_auth(outsider_token)
    )
    assert listing.status_code == 403
    assert listing.json()["detail"] == "lab membership required (any role)"
    assert (
        client.get(
            f"/api/v1/labs/{lab['id']}/wiki/{page_id}", headers=_auth(outsider_token)
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/labs/{lab['id']}/wiki",
            json={"title": "Injected", "content": "x", "tags": []},
            headers=_auth(outsider_token),
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/v1/labs/{lab['id']}/wiki/{page_id}",
            json={"content": "tampered"},
            headers=_auth(outsider_token),
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/v1/labs/{lab['id']}/wiki/{page_id}", headers=_auth(outsider_token)
        ).status_code
        == 403
    )

    # a plain member in the lowest role may still read it
    visitor, visitor_token = _make_user(client, tmp_db, "visitor_user")
    add_member(tmp_db, lab["id"], visitor.id, "visitor")
    member_view = client.get(
        f"/api/v1/labs/{lab['id']}/wiki", headers=_auth(visitor_token)
    )
    assert member_view.status_code == 200
    assert [p["id"] for p in member_view.json()] == [page_id]
    assert (
        client.get(
            f"/api/v1/labs/{lab['id']}/wiki/slug/{page.json()['slug']}",
            headers=_auth(visitor_token),
        ).status_code
        == 200
    )


def test_wiki_allows_platform_admin(client, tmp_db, admin_token) -> None:
    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    resp = client.get(f"/api/v1/labs/{lab['id']}/wiki", headers=_auth(admin_token))
    assert resp.status_code == 200


# ── Research impact is members-only ──────────────────────────────────────────


def test_research_impact_refuses_non_member_and_allows_member(client, tmp_db) -> None:
    from gazzali.crud.labs import add_member

    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")

    refused = client.get(
        f"/api/v1/labs/{lab['id']}/research-impact", headers=_auth(outsider_token)
    )
    assert refused.status_code == 403
    assert refused.json()["detail"] == "lab membership required (any role)"

    member, member_token = _make_user(client, tmp_db, "member_user")
    add_member(tmp_db, lab["id"], member.id, "phd")
    allowed = client.get(
        f"/api/v1/labs/{lab['id']}/research-impact", headers=_auth(member_token)
    )
    assert allowed.status_code == 200
    assert allowed.json()["lab_id"] == lab["id"]


# ── /pi/stats no longer falls open to every lab ──────────────────────────────


def _lab_with_project(client, tmp_db, pi_token, lab_name, project_name):
    lab = client.post(
        "/api/v1/labs", json={"name": lab_name}, headers=_auth(pi_token)
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={"name": project_name, "lab_id": lab["id"]},
        headers=_auth(pi_token),
    )
    assert project.status_code == 201
    return lab


def test_pi_stats_leads_nothing_sees_zeros_not_every_lab(client, tmp_db) -> None:
    """Regression test for the fail-open fallback that leaked platform-wide stats."""
    _pi, pi_token = _make_user(client, tmp_db, "pi_user")
    _lab_with_project(client, tmp_db, pi_token, "Other Lab", "Other Project")

    _stranger, stranger_token = _make_user(client, tmp_db, "stranger")
    resp = client.get("/api/v1/pi/stats", headers=_auth(stranger_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["labs"] == []
    assert data["recent_projects"] == []
    assert data["total_tasks"] == 0
    assert data["total_experiments"] == 0
    # the empty answer still carries the full shape so the UI does not break
    for key in (
        "task_statuses",
        "experiment_statuses",
        "publication_statuses",
        "publications_over_time",
        "mentorship",
    ):
        assert key in data


def test_pi_stats_non_pi_member_sees_zeros(client, tmp_db) -> None:
    from gazzali.crud.labs import add_member

    _pi, pi_token = _make_user(client, tmp_db, "pi_user")
    lab = _lab_with_project(client, tmp_db, pi_token, "Imaging Lab", "Imaging Project")

    student, student_token = _make_user(client, tmp_db, "student")
    add_member(tmp_db, lab["id"], student.id, "ms")

    data = client.get("/api/v1/pi/stats", headers=_auth(student_token)).json()
    assert data["labs"] == []
    assert data["recent_projects"] == []


def test_pi_stats_matches_pi_row_when_pi_id_is_null(client, tmp_db) -> None:
    """Production labs have pi_id NULL — the 'pi' lab_members row must still match."""
    from gazzali.db import get_db

    _pi, pi_token = _make_user(client, tmp_db, "pi_user")
    lab = _lab_with_project(client, tmp_db, pi_token, "Imaging Lab", "Imaging Project")
    with get_db(tmp_db) as conn:
        conn.execute("UPDATE labs SET pi_id = NULL WHERE id = ?", (lab["id"],))

    data = client.get("/api/v1/pi/stats", headers=_auth(pi_token)).json()
    assert [entry["id"] for entry in data["labs"]] == [lab["id"]]
    assert [p["name"] for p in data["recent_projects"]] == ["Imaging Project"]


def test_pi_stats_only_own_labs(client, tmp_db) -> None:
    _pi_a, pi_a_token = _make_user(client, tmp_db, "pi_a")
    lab_a = _lab_with_project(client, tmp_db, pi_a_token, "Lab A", "Project A")
    _pi_b, pi_b_token = _make_user(client, tmp_db, "pi_b")
    _lab_with_project(client, tmp_db, pi_b_token, "Lab B", "Project B")

    data = client.get("/api/v1/pi/stats", headers=_auth(pi_a_token)).json()
    assert [entry["id"] for entry in data["labs"]] == [lab_a["id"]]
    assert [p["name"] for p in data["recent_projects"]] == ["Project A"]


def test_pi_stats_platform_admin_sees_all_labs(client, tmp_db, admin_token) -> None:
    _pi_a, pi_a_token = _make_user(client, tmp_db, "pi_a")
    lab_a = _lab_with_project(client, tmp_db, pi_a_token, "Lab A", "Project A")
    _pi_b, pi_b_token = _make_user(client, tmp_db, "pi_b")
    lab_b = _lab_with_project(client, tmp_db, pi_b_token, "Lab B", "Project B")

    data = client.get("/api/v1/pi/stats", headers=_auth(admin_token)).json()
    assert {entry["id"] for entry in data["labs"]} == {lab_a["id"], lab_b["id"]}


# ── membership is a LIFECYCLE (increment 5): ended, not erased ────────────────


def test_removed_member_is_ended_not_erased_and_readd_reactivates(client, tmp_db) -> None:
    from gazzali.crud.labs import get_member_role
    from gazzali.db import get_db

    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    student, student_token = _make_user(client, tmp_db, "leaver")
    client.post(f"/api/v1/labs/{lab['id']}/members",
                json={"user_id": student.id, "role": "ms"}, headers=_auth(pi_token))
    assert get_member_role(tmp_db, lab["id"], student.id) == "ms"

    r = client.delete(f"/api/v1/labs/{lab['id']}/members/{student.id}", headers=_auth(pi_token))
    assert r.status_code in (200, 204)
    # authz gone immediately...
    assert get_member_role(tmp_db, lab["id"], student.id) is None
    # ...but the ROW survives with ended_at — the revocation order the reconciler executes
    with get_db(tmp_db) as conn:
        row = conn.execute(
            "SELECT ended_at FROM lab_members WHERE lab_id=? AND user_id=?",
            (lab["id"], student.id)).fetchone()
    assert row is not None and row["ended_at"]

    # re-adding re-activates the same row
    r = client.post(f"/api/v1/labs/{lab['id']}/members",
                    json={"user_id": student.id, "role": "phd"}, headers=_auth(pi_token))
    assert r.status_code == 201
    assert get_member_role(tmp_db, lab["id"], student.id) == "phd"
    with get_db(tmp_db) as conn:
        row = conn.execute(
            "SELECT ended_at FROM lab_members WHERE lab_id=? AND user_id=?",
            (lab["id"], student.id)).fetchone()
    assert row["ended_at"] is None
