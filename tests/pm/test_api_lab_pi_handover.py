"""Handing a lab to its real PI, and keeping a lab from losing its PI through the roster.

Every PI power (dataset approval, sharing, revocation, the ethics record, managing the roster)
reads the lab_members role, never labs.pi_id. A handover that moved only pi_id therefore gave
the new PI the title without the powers; and a co-PI or lab admin could demote or remove the
PI, leaving a lab only a platform admin could repair."""

from gazzali.crud.labs import add_member, get_lab, get_member_role


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
        role="professor",
    )
    token = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    ).json()["token"]
    return user, token


def _lab(client, tmp_db):
    """A lab created by `creator` (its PI), with `real_pi` as a postdoc and `co_pi` as a second
    'pi'-role member."""
    creator, creator_token = _make_user(client, tmp_db, "creator")
    r = client.post("/api/v1/labs", json={"name": "Bone Lab"}, headers=_auth(creator_token))
    assert r.status_code == 201, r.text
    lab = r.json()
    real_pi, real_pi_token = _make_user(client, tmp_db, "real_pi")
    co_pi, co_pi_token = _make_user(client, tmp_db, "co_pi")
    add_member(tmp_db, lab["id"], real_pi.id, "postdoc")
    add_member(tmp_db, lab["id"], co_pi.id, "pi")
    return lab, (creator, creator_token), (real_pi, real_pi_token), (co_pi, co_pi_token)


def test_the_new_pi_gets_the_pi_role_with_the_title(client, tmp_db) -> None:
    lab, (creator, creator_token), (real_pi, real_pi_token), _ = _lab(client, tmp_db)

    r = client.put(f"/api/v1/labs/{lab['id']}", json={"pi_id": real_pi.id},
                   headers=_auth(creator_token))
    assert r.status_code == 200, r.text
    assert get_lab(tmp_db, lab["id"]).pi_id == real_pi.id
    assert get_member_role(tmp_db, lab["id"], real_pi.id) == "pi"
    # the previous PI keeps their role until someone changes it
    assert get_member_role(tmp_db, lab["id"], creator.id) == "pi"

    # and the powers come with it: the new PI can manage the roster
    newcomer, _ = _make_user(client, tmp_db, "newcomer")
    r = client.post(f"/api/v1/labs/{lab['id']}/members",
                    json={"user_id": newcomer.id, "role": "ms"}, headers=_auth(real_pi_token))
    assert r.status_code == 201, r.text


def test_after_the_handover_the_new_pi_can_step_the_old_one_down(client, tmp_db) -> None:
    lab, (creator, creator_token), (real_pi, real_pi_token), _ = _lab(client, tmp_db)
    client.put(f"/api/v1/labs/{lab['id']}", json={"pi_id": real_pi.id},
               headers=_auth(creator_token))

    r = client.put(f"/api/v1/labs/{lab['id']}/members/{creator.id}", json={"role": "postdoc"},
                   headers=_auth(real_pi_token))
    assert r.status_code == 200, r.text
    assert get_member_role(tmp_db, lab["id"], creator.id) == "postdoc"


def test_the_lab_pi_cannot_be_demoted_through_the_roster(client, tmp_db) -> None:
    lab, (creator, creator_token), _, (_co_pi, co_pi_token) = _lab(client, tmp_db)
    for token in (co_pi_token, creator_token):  # a co-PI, and the PI themself
        r = client.put(f"/api/v1/labs/{lab['id']}/members/{creator.id}", json={"role": "ms"},
                       headers=_auth(token))
        assert r.status_code == 409, r.text
        assert "hand the lab" in r.json()["detail"]
    assert get_member_role(tmp_db, lab["id"], creator.id) == "pi"


def test_the_lab_pi_cannot_be_removed_through_the_roster(client, tmp_db) -> None:
    lab, (creator, creator_token), _, (_co_pi, co_pi_token) = _lab(client, tmp_db)
    for token in (co_pi_token, creator_token):
        r = client.delete(f"/api/v1/labs/{lab['id']}/members/{creator.id}",
                          headers=_auth(token))
        assert r.status_code == 409, r.text
    assert get_member_role(tmp_db, lab["id"], creator.id) == "pi"


def test_other_members_are_still_managed_as_before(client, tmp_db) -> None:
    lab, _, (real_pi, _), (_co_pi, co_pi_token) = _lab(client, tmp_db)
    r = client.put(f"/api/v1/labs/{lab['id']}/members/{real_pi.id}", json={"role": "phd"},
                   headers=_auth(co_pi_token))
    assert r.status_code == 200, r.text
    r = client.delete(f"/api/v1/labs/{lab['id']}/members/{real_pi.id}",
                      headers=_auth(co_pi_token))
    assert r.status_code == 204, r.text


def test_a_platform_admin_can_still_repair_directly(client, tmp_db) -> None:
    lab, (creator, _), _, _ = _lab(client, tmp_db)
    _admin, admin_token = _make_user(client, tmp_db, "root", is_admin=True)
    r = client.put(f"/api/v1/labs/{lab['id']}/members/{creator.id}", json={"role": "postdoc"},
                   headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    r = client.delete(f"/api/v1/labs/{lab['id']}/members/{creator.id}",
                      headers=_auth(admin_token))
    assert r.status_code == 204, r.text


def test_setting_the_pi_role_on_the_pi_is_harmless(client, tmp_db) -> None:
    lab, (creator, creator_token), _, _ = _lab(client, tmp_db)
    r = client.put(f"/api/v1/labs/{lab['id']}/members/{creator.id}", json={"role": "pi"},
                   headers=_auth(creator_token))
    assert r.status_code == 200, r.text


# ── Labs with no PI on record (pi_id NULL — the oldest labs) ──────────────────


def _legacy(client, tmp_db):
    """The same lab with pi_id cleared, as labs created before pi_id was recorded are."""
    from gazzali.db import get_db

    parts = _lab(client, tmp_db)
    with get_db(tmp_db) as conn:
        conn.execute("UPDATE labs SET pi_id = NULL WHERE id = ?", (parts[0]["id"],))
    return parts


def test_without_a_recorded_pi_a_co_pi_cannot_remove_or_demote_the_other(client, tmp_db) -> None:
    lab, (creator, _), _, (_co_pi, co_pi_token) = _legacy(client, tmp_db)
    r = client.delete(f"/api/v1/labs/{lab['id']}/members/{creator.id}", headers=_auth(co_pi_token))
    assert r.status_code == 409, r.text
    r = client.put(f"/api/v1/labs/{lab['id']}/members/{creator.id}", json={"role": "ms"},
                   headers=_auth(co_pi_token))
    assert r.status_code == 409, r.text
    assert get_member_role(tmp_db, lab["id"], creator.id) == "pi"


def test_without_a_recorded_pi_nobody_claims_the_lab_while_several_hold_the_role(client, tmp_db) -> None:
    """The takeover: a co-PI set pi_id to themselves, then removed the real PI."""
    lab, _, _, (co_pi, co_pi_token) = _legacy(client, tmp_db)
    r = client.put(f"/api/v1/labs/{lab['id']}", json={"pi_id": co_pi.id}, headers=_auth(co_pi_token))
    assert r.status_code == 403, r.text
    assert get_lab(tmp_db, lab["id"]).pi_id is None


def test_without_a_recorded_pi_the_sole_pi_cannot_lock_themselves_out(client, tmp_db) -> None:
    lab, (creator, creator_token), _, (co_pi, _) = _legacy(client, tmp_db)
    from gazzali.crud.labs import remove_member

    remove_member(tmp_db, lab["id"], co_pi.id)            # the creator is now the only 'pi'
    r = client.put(f"/api/v1/labs/{lab['id']}/members/{creator.id}", json={"role": "phd"},
                   headers=_auth(creator_token))
    assert r.status_code == 409, r.text
    # ...but may still record themselves as the PI (the legacy repair), and then hand over
    r = client.put(f"/api/v1/labs/{lab['id']}", json={"pi_id": creator.id},
                   headers=_auth(creator_token))
    assert r.status_code == 200, r.text


def test_without_a_recorded_pi_a_platform_admin_decides(client, tmp_db) -> None:
    lab, (creator, _), _, (co_pi, _) = _legacy(client, tmp_db)
    _admin, admin_token = _make_user(client, tmp_db, "root", is_admin=True)
    r = client.put(f"/api/v1/labs/{lab['id']}", json={"pi_id": creator.id}, headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    r = client.put(f"/api/v1/labs/{lab['id']}/members/{co_pi.id}", json={"role": "postdoc"},
                   headers=_auth(admin_token))
    assert r.status_code == 200, r.text


def test_without_a_recorded_pi_nobody_else_is_made_a_pi_by_a_non_admin(client, tmp_db) -> None:
    """Every PI-role member of such a lab is protected, so a promotion there could never be undone
    by a non-admin — a one-way ratchet handing out PI powers. Refused, by role change and by add."""
    lab, (_creator, creator_token), (real_pi, _), (co_pi, _) = _legacy(client, tmp_db)
    from gazzali.crud.labs import remove_member

    remove_member(tmp_db, lab["id"], co_pi.id)            # the creator is the sole PI-role member
    r = client.put(f"/api/v1/labs/{lab['id']}/members/{real_pi.id}", json={"role": "pi"},
                   headers=_auth(creator_token))
    assert r.status_code == 409, r.text
    assert get_member_role(tmp_db, lab["id"], real_pi.id) == "postdoc"
    newcomer, _ = _make_user(client, tmp_db, "newcomer")
    r = client.post(f"/api/v1/labs/{lab['id']}/members", json={"user_id": newcomer.id, "role": "pi"},
                    headers=_auth(creator_token))
    assert r.status_code == 409, r.text
    assert get_member_role(tmp_db, lab["id"], newcomer.id) is None
    # other roles are added and changed as before
    r = client.put(f"/api/v1/labs/{lab['id']}/members/{real_pi.id}", json={"role": "phd"},
                   headers=_auth(creator_token))
    assert r.status_code == 200, r.text


def test_once_the_pi_is_recorded_promotions_work_again(client, tmp_db) -> None:
    lab, (creator, creator_token), (real_pi, _), (co_pi, _) = _legacy(client, tmp_db)
    from gazzali.crud.labs import remove_member

    remove_member(tmp_db, lab["id"], co_pi.id)
    assert client.put(f"/api/v1/labs/{lab['id']}", json={"pi_id": creator.id},
                      headers=_auth(creator_token)).status_code == 200
    r = client.put(f"/api/v1/labs/{lab['id']}/members/{real_pi.id}", json={"role": "pi"},
                   headers=_auth(creator_token))
    assert r.status_code == 200, r.text


def test_a_platform_admin_may_still_add_a_pi_to_a_lab_with_none_recorded(client, tmp_db) -> None:
    lab, _, (real_pi, _), _ = _legacy(client, tmp_db)
    _admin, admin_token = _make_user(client, tmp_db, "root", is_admin=True)
    r = client.put(f"/api/v1/labs/{lab['id']}/members/{real_pi.id}", json={"role": "pi"},
                   headers=_auth(admin_token))
    assert r.status_code == 200, r.text
