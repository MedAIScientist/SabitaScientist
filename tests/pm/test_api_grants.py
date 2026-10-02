"""Tests for /grants authorization: who may see a grant, and who may change it."""


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_user(client, tmp_db, username, password="pw", is_admin=False):
    """Create a user in the temp DB and return (user, token)."""
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


def _lab_with_pi(client, tmp_db, name="Imaging Lab"):
    """Create a non-admin PI plus a lab they created. Returns (lab, pi, pi_token)."""
    pi, pi_token = _make_user(client, tmp_db, "pi_user")
    resp = client.post("/api/v1/labs", json={"name": name}, headers=_auth(pi_token))
    assert resp.status_code == 201
    return resp.json(), pi, pi_token


def _project_with_owner(client, tmp_db, name="Imaging Project"):
    """Create a non-admin owner plus a project they created."""
    owner, owner_token = _make_user(client, tmp_db, "owner_user")
    resp = client.post(
        "/api/v1/projects", json={"name": name}, headers=_auth(owner_token)
    )
    assert resp.status_code == 201
    return resp.json(), owner, owner_token


def _grant(client, token, **body):
    """POST a grant as the holder of token and return the response JSON."""
    payload = {"title": "R01", "funder": "NIH", "amount_awarded": 50000, **body}
    resp = client.post("/api/v1/grants", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── An outsider sees nothing and can change nothing ───────────────────────────


def test_outsider_list_excludes_other_groups_grants(client, tmp_db) -> None:
    """The live hole: every authenticated user could read every grant's funding."""
    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    grant = _grant(client, pi_token, lab_id=lab["id"])

    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")
    resp = client.get("/api/v1/grants", headers=_auth(outsider_token))
    assert resp.status_code == 200
    assert [g["id"] for g in resp.json()] == []
    # and the lab PI still sees their own
    mine = client.get("/api/v1/grants", headers=_auth(pi_token)).json()
    assert [g["id"] for g in mine] == [grant["id"]]


def test_outsider_get_by_id_is_404_not_403(client, tmp_db) -> None:
    """A grant nobody may see answers like a grant that is not there."""
    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    grant = _grant(client, pi_token, lab_id=lab["id"])

    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")
    resp = client.get(f"/api/v1/grants/{grant['id']}", headers=_auth(outsider_token))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Grant not found"


def test_outsider_cannot_update_or_delete(client, tmp_db) -> None:
    from EvoScientist.pm.crud.grants import get_grant

    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    grant = _grant(client, pi_token, lab_id=lab["id"])

    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")
    update = client.put(
        f"/api/v1/grants/{grant['id']}",
        json={"amount_awarded": 1},
        headers=_auth(outsider_token),
    )
    assert update.status_code == 404
    delete = client.delete(
        f"/api/v1/grants/{grant['id']}", headers=_auth(outsider_token)
    )
    assert delete.status_code == 404
    # neither attempt touched the row
    stored = get_grant(tmp_db, grant["id"])
    assert stored is not None
    assert stored.amount_awarded == 50000


def test_outsider_cannot_create_grant_for_someone_elses_lab(client, tmp_db) -> None:
    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")

    resp = client.post(
        "/api/v1/grants",
        json={"title": "Injected", "funder": "NIH", "lab_id": lab["id"]},
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403
    assert "pi" in resp.json()["detail"]


def test_explicit_lab_filter_by_non_member_is_403(client, tmp_db) -> None:
    """An explicit ask earns an explicit refusal, not a misleading empty page."""
    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    _outsider, outsider_token = _make_user(client, tmp_db, "outsider")

    resp = client.get(
        f"/api/v1/grants?lab_id={lab['id']}", headers=_auth(outsider_token)
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "lab membership required (any role)"


# ── Lab roles: any role reads, 'pi'/'admin' writes ────────────────────────────


def test_lab_pi_can_read_and_write(client, tmp_db) -> None:
    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    grant = _grant(client, pi_token, lab_id=lab["id"])

    got = client.get(f"/api/v1/grants/{grant['id']}", headers=_auth(pi_token))
    assert got.status_code == 200
    assert got.json()["funder"] == "NIH"

    updated = client.put(
        f"/api/v1/grants/{grant['id']}",
        json={"status": "awarded"},
        headers=_auth(pi_token),
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "awarded"

    assert (
        client.delete(
            f"/api/v1/grants/{grant['id']}", headers=_auth(pi_token)
        ).status_code
        == 204
    )


def test_lab_admin_member_can_write(client, tmp_db) -> None:
    from EvoScientist.pm.crud.labs import add_member

    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    grant = _grant(client, pi_token, lab_id=lab["id"])
    lab_admin, lab_admin_token = _make_user(client, tmp_db, "lab_admin")
    add_member(tmp_db, lab["id"], lab_admin.id, "admin")

    resp = client.put(
        f"/api/v1/grants/{grant['id']}",
        json={"funder": "TUBITAK"},
        headers=_auth(lab_admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["funder"] == "TUBITAK"


def test_lab_ms_member_reads_but_cannot_write(client, tmp_db) -> None:
    from EvoScientist.pm.crud.grants import get_grant
    from EvoScientist.pm.crud.labs import add_member

    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    grant = _grant(client, pi_token, lab_id=lab["id"])
    student, student_token = _make_user(client, tmp_db, "student")
    add_member(tmp_db, lab["id"], student.id, "ms")

    listing = client.get("/api/v1/grants", headers=_auth(student_token))
    assert [g["id"] for g in listing.json()] == [grant["id"]]
    assert (
        client.get(
            f"/api/v1/grants/{grant['id']}", headers=_auth(student_token)
        ).status_code
        == 200
    )
    # the lab_id filter is theirs to use as well
    assert (
        client.get(
            f"/api/v1/grants?lab_id={lab['id']}", headers=_auth(student_token)
        ).status_code
        == 200
    )

    update = client.put(
        f"/api/v1/grants/{grant['id']}",
        json={"amount_awarded": 999},
        headers=_auth(student_token),
    )
    assert update.status_code == 403
    assert "platform admin" in update.json()["detail"]
    delete = client.delete(
        f"/api/v1/grants/{grant['id']}", headers=_auth(student_token)
    )
    assert delete.status_code == 403
    assert get_grant(tmp_db, grant["id"]).amount_awarded == 50000


# ── Project roles: any role reads, 'owner'/'editor' writes ────────────────────


def test_project_owner_can_read_and_write(client, tmp_db) -> None:
    project, _owner, owner_token = _project_with_owner(client, tmp_db)
    grant = _grant(client, owner_token, project_id=project["id"])

    assert (
        client.get(
            f"/api/v1/grants/{grant['id']}", headers=_auth(owner_token)
        ).status_code
        == 200
    )
    resp = client.put(
        f"/api/v1/grants/{grant['id']}",
        json={"status": "submitted"},
        headers=_auth(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"


def test_project_editor_can_write(client, tmp_db) -> None:
    from EvoScientist.pm.crud.projects import add_member

    project, _owner, owner_token = _project_with_owner(client, tmp_db)
    grant = _grant(client, owner_token, project_id=project["id"])
    editor, editor_token = _make_user(client, tmp_db, "editor_user")
    add_member(tmp_db, project["id"], editor.id, "editor")

    resp = client.put(
        f"/api/v1/grants/{grant['id']}",
        json={"amount_requested": 120000},
        headers=_auth(editor_token),
    )
    assert resp.status_code == 200
    assert resp.json()["amount_requested"] == 120000


def test_project_viewer_reads_but_cannot_write(client, tmp_db) -> None:
    from EvoScientist.pm.crud.projects import add_member

    project, _owner, owner_token = _project_with_owner(client, tmp_db)
    grant = _grant(client, owner_token, project_id=project["id"])
    viewer, viewer_token = _make_user(client, tmp_db, "viewer_user")
    add_member(tmp_db, project["id"], viewer.id, "viewer")

    assert (
        client.get(
            f"/api/v1/grants/{grant['id']}", headers=_auth(viewer_token)
        ).status_code
        == 200
    )
    assert [
        g["id"]
        for g in client.get("/api/v1/grants", headers=_auth(viewer_token)).json()
    ] == [grant["id"]]

    update = client.put(
        f"/api/v1/grants/{grant['id']}",
        json={"amount_awarded": 1},
        headers=_auth(viewer_token),
    )
    assert update.status_code == 403
    assert (
        client.delete(
            f"/api/v1/grants/{grant['id']}", headers=_auth(viewer_token)
        ).status_code
        == 403
    )


# ── A grant attached to neither a lab nor a project ──────────────────────────


def test_unattached_grant_belongs_to_its_creator_only(client, tmp_db) -> None:
    _creator, creator_token = _make_user(client, tmp_db, "creator")
    grant = _grant(client, creator_token)

    assert (
        client.get(
            f"/api/v1/grants/{grant['id']}", headers=_auth(creator_token)
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/grants/{grant['id']}",
            json={"status": "submitted"},
            headers=_auth(creator_token),
        ).status_code
        == 200
    )

    _stranger, stranger_token = _make_user(client, tmp_db, "stranger")
    assert (
        client.get(
            f"/api/v1/grants/{grant['id']}", headers=_auth(stranger_token)
        ).status_code
        == 404
    )
    assert [
        g["id"]
        for g in client.get("/api/v1/grants", headers=_auth(stranger_token)).json()
    ] == []
    assert (
        client.delete(
            f"/api/v1/grants/{grant['id']}", headers=_auth(stranger_token)
        ).status_code
        == 404
    )


def test_unattached_grant_readable_and_writable_by_its_named_pi(client, tmp_db) -> None:
    """pi_id is the other half of "whose grant is this" — not only created_by."""
    named_pi, named_pi_token = _make_user(client, tmp_db, "named_pi")
    _creator, creator_token = _make_user(client, tmp_db, "creator")
    grant = _grant(client, creator_token, pi_id=named_pi.id)

    assert (
        client.get(
            f"/api/v1/grants/{grant['id']}", headers=_auth(named_pi_token)
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/grants/{grant['id']}",
            json={"status": "submitted"},
            headers=_auth(named_pi_token),
        ).status_code
        == 200
    )


def test_unattached_grant_cannot_be_pushed_into_a_foreign_lab(client, tmp_db) -> None:
    """Re-targeting is a write against the destination as well as the source."""
    from EvoScientist.pm.crud.grants import get_grant

    lab, _pi, _pi_token = _lab_with_pi(client, tmp_db)
    _creator, creator_token = _make_user(client, tmp_db, "creator")
    grant = _grant(client, creator_token)

    resp = client.put(
        f"/api/v1/grants/{grant['id']}",
        json={"lab_id": lab["id"]},
        headers=_auth(creator_token),
    )
    assert resp.status_code == 403
    assert get_grant(tmp_db, grant["id"]).lab_id is None


# ── Create validates the lab/project it names ────────────────────────────────


def test_create_rejects_unknown_lab_and_project(client, tmp_db, admin_token) -> None:
    lab_resp = client.post(
        "/api/v1/grants",
        json={"title": "Ghost", "funder": "NIH", "lab_id": "nope"},
        headers=_auth(admin_token),
    )
    assert lab_resp.status_code == 400
    assert lab_resp.json()["detail"] == "Lab not found"

    project_resp = client.post(
        "/api/v1/grants",
        json={"title": "Ghost", "funder": "NIH", "project_id": "nope"},
        headers=_auth(admin_token),
    )
    assert project_resp.status_code == 400
    assert project_resp.json()["detail"] == "Project not found"


# ── The platform admin is the superuser here too ──────────────────────────────


def test_platform_admin_can_read_and_write_any_grant(
    client, tmp_db, admin_token
) -> None:
    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    grant = _grant(client, pi_token, lab_id=lab["id"])

    listing = client.get("/api/v1/grants", headers=_auth(admin_token))
    assert [g["id"] for g in listing.json()] == [grant["id"]]
    assert (
        client.get(
            f"/api/v1/grants/{grant['id']}", headers=_auth(admin_token)
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/grants?lab_id={lab['id']}", headers=_auth(admin_token)
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/grants/{grant['id']}",
            json={"status": "awarded"},
            headers=_auth(admin_token),
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/v1/grants/{grant['id']}", headers=_auth(admin_token)
        ).status_code
        == 204
    )


# ── Pagination walks the visible grants, not the whole table ─────────────────


def test_pagination_is_applied_after_the_visibility_filter(client, tmp_db) -> None:
    """Otherwise page 1 could be all withheld rows and look like "no grants"."""
    lab, _pi, pi_token = _lab_with_pi(client, tmp_db)
    _other_pi, other_pi_token = _make_user(client, tmp_db, "other_pi")
    other_lab = client.post(
        "/api/v1/labs", json={"name": "Other Lab"}, headers=_auth(other_pi_token)
    ).json()
    for i in range(3):
        _grant(client, other_pi_token, lab_id=other_lab["id"], title=f"Theirs {i}")
    mine = _grant(client, pi_token, lab_id=lab["id"], title="Mine")

    page = client.get("/api/v1/grants?offset=0&limit=2", headers=_auth(pi_token))
    assert [g["id"] for g in page.json()] == [mine["id"]]
