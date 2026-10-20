"""Who may put a new project in a lab. The Projects page now offers a lab picker, so the
rule it relies on is enforced by the API rather than by which labs the picker lists:
a project in a lab moves into that lab's CVAT organisation and under its PI, so only a
member of the lab (any role) or a platform admin may create one there."""

import pytest


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_user(client, tmp_db, username, password="pw", is_admin=False, role="professor"):
    from gazzali.auth import hash_password
    from gazzali.crud.users import create_user

    user = create_user(
        tmp_db,
        username=username,
        password_hash=hash_password(password),
        is_admin=is_admin,
        role=role,
    )
    token = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    ).json()["token"]
    return user, token


@pytest.fixture
def lab(client, tmp_db):
    """A lab led by pi_user, with student1 as an ms member. Returns (lab, tokens)."""
    _pi, pi_token = _make_user(client, tmp_db, "pi_user")
    r = client.post("/api/v1/labs", json={"name": "Test Lab"}, headers=_auth(pi_token))
    assert r.status_code == 201, r.text
    lab = r.json()
    student, student_token = _make_user(client, tmp_db, "student1", role="student")
    r = client.post(
        f"/api/v1/labs/{lab['id']}/members",
        json={"user_id": student.id, "role": "ms"},
        headers=_auth(pi_token),
    )
    assert r.status_code in (200, 201), r.text
    outsider, outsider_token = _make_user(client, tmp_db, "outsider")
    _admin, admin_token = _make_user(client, tmp_db, "root", is_admin=True)
    return lab, {
        "pi": pi_token,
        "student": student_token,
        "outsider": outsider_token,
        "admin": admin_token,
        "outsider_id": outsider.id,
    }


def _create(client, token, lab_id, via):
    if via == "plain":
        return client.post(
            "/api/v1/projects",
            json={"name": "Ankle study", "lab_id": lab_id},
            headers=_auth(token),
        )
    return client.post(
        "/api/v1/templates/from-template",
        json={"template_id": "medical", "name": "Ankle study", "lab_id": lab_id},
        headers=_auth(token),
    )


VIA = ["plain", "template"]


@pytest.mark.parametrize("via", VIA)
@pytest.mark.parametrize("who", ["pi", "student", "admin"])
def test_a_member_or_an_admin_creates_the_project_in_the_lab(client, tmp_db, lab, via, who):
    from gazzali.crud.projects import get_project

    the_lab, tokens = lab
    r = _create(client, tokens[who], the_lab["id"], via)
    assert r.status_code == 201, r.text
    assert r.json()["lab_id"] == the_lab["id"]
    assert get_project(tmp_db, r.json()["id"]).lab_id == the_lab["id"]


@pytest.mark.parametrize("via", VIA)
def test_an_outsider_cannot_put_a_project_in_someone_elses_lab(client, tmp_db, lab, via):
    from gazzali.crud.projects import list_projects_for_user

    the_lab, tokens = lab
    r = _create(client, tokens["outsider"], the_lab["id"], via)
    assert r.status_code == 403, r.text
    # refused before anything is written: no half-made project is left behind
    assert list_projects_for_user(tmp_db, tokens["outsider_id"]) == []


@pytest.mark.parametrize("via", VIA)
def test_an_unknown_lab_is_a_clear_error(client, tmp_db, lab, via):
    _the_lab, tokens = lab
    r = _create(client, tokens["admin"], "no-such-lab", via)
    assert r.status_code == 400, r.text
    assert "lab does not exist" in r.text


@pytest.mark.parametrize("via", VIA)
def test_no_lab_stays_open_to_everyone(client, tmp_db, lab, via):
    _the_lab, tokens = lab
    r = _create(client, tokens["outsider"], None, via)
    assert r.status_code == 201, r.text
    assert r.json()["lab_id"] is None
