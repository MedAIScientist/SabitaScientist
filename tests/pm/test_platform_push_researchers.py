"""The researcher membership push — the last mile of the imaging path.

A delivered cohort lands in a bucket the PROJECT may read. A person's notebook
holds a session key that opens only their own workspace, so unless Medai tells
platform-control which projects someone is an active member of, the researcher
the data was delivered for cannot open it. These tests pin down what is pushed,
when, and — the property that matters most in production — that a push failure
never costs a governance write.
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError

import pytest

from gazzali import platform_push
from gazzali.crud.projects import add_member, create_project, remove_member
from gazzali.crud.researchers import bump_researcher_generation, researcher_generation
from gazzali.crud.users import create_user
from gazzali.auth import hash_password


@pytest.fixture
def pushes(monkeypatch):
    """Capture every PUT the push client makes, without touching the network."""
    captured: list[dict] = []

    class _Resp:
        status = 200

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def _urlopen(req, timeout=None, context=None):
        captured.append(
            {
                "url": req.full_url,
                "method": req.get_method(),
                "body": json.loads(req.data.decode()) if req.data else None,
            }
        )
        return _Resp()

    monkeypatch.setattr(platform_push.urllib.request, "urlopen", _urlopen)
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_URL", "https://platform.example/")
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_TOKEN", "t0ken")
    monkeypatch.delenv("MEDAI_PLATFORM_CONTROL_CA", raising=False)
    return captured


def _user(db, name, email):
    return create_user(db, username=name, password_hash=hash_password("p"), email=email)


# ── the generation counter ───────────────────────────────────────────────────


def test_generation_is_monotonic_per_person(tmp_db) -> None:
    assert researcher_generation(tmp_db, "a@x.co") == 0
    assert bump_researcher_generation(tmp_db, "a@x.co") == 1
    assert bump_researcher_generation(tmp_db, "a@x.co") == 2
    # Independent per person, and case-folded to one identity.
    assert bump_researcher_generation(tmp_db, "b@x.co") == 1
    assert bump_researcher_generation(tmp_db, "A@X.CO") == 3
    assert researcher_generation(tmp_db, "a@x.co") == 3


# ── what the document says ───────────────────────────────────────────────────


def test_build_researcher_state_lists_active_projects(tmp_db) -> None:
    u = _user(tmp_db, "ahmed", "Ahmed.Sallam@STD.Medipol.Edu.TR")
    p1 = create_project(tmp_db, name="one", description=None, created_by=u.id)
    p2 = create_project(tmp_db, name="two", description=None, created_by=u.id)

    doc = platform_push.build_researcher_state(tmp_db, "ahmed.sallam@std.medipol.edu.tr")
    assert doc["email"] == "ahmed.sallam@std.medipol.edu.tr"
    assert sorted(doc["projects"]) == sorted([p1.id, p2.id])
    assert doc["generation"] == 1
    # The next build bumps the generation, so two pushes never collide.
    assert platform_push.build_researcher_state(tmp_db, u.email)["generation"] == 2


def test_build_researcher_state_excludes_archived_projects(tmp_db) -> None:
    from gazzali.crud.projects import update_project

    u = _user(tmp_db, "ahmed", "a@x.co")
    live = create_project(tmp_db, name="live", description=None, created_by=u.id)
    dead = create_project(tmp_db, name="dead", description=None, created_by=u.id)
    update_project(tmp_db, dead.id, archived_at="2026-08-01T00:00:00Z")

    doc = platform_push.build_researcher_state(tmp_db, "a@x.co")
    assert doc["projects"] == [live.id]


def test_build_researcher_state_needs_an_address(tmp_db) -> None:
    assert platform_push.build_researcher_state(tmp_db, "") is None
    assert platform_push.build_researcher_state(tmp_db, "   ") is None


def test_a_membership_that_ended_leaves_the_document(tmp_db) -> None:
    owner = _user(tmp_db, "owner", "o@x.co")
    member = _user(tmp_db, "member", "m@x.co")
    proj = create_project(tmp_db, name="p", description=None, created_by=owner.id)
    add_member(tmp_db, project_id=proj.id, user_id=member.id, role="editor")
    assert platform_push.build_researcher_state(tmp_db, "m@x.co")["projects"] == [proj.id]

    remove_member(tmp_db, project_id=proj.id, user_id=member.id)
    # The push is the FULL current set, so a hard delete needs no soft-delete
    # column: the shorter list IS the revocation.
    assert platform_push.build_researcher_state(tmp_db, "m@x.co")["projects"] == []


# ── the push itself ──────────────────────────────────────────────────────────


def test_push_is_a_no_op_when_unconfigured(tmp_db, monkeypatch) -> None:
    monkeypatch.delenv("MEDAI_PLATFORM_CONTROL_URL", raising=False)
    monkeypatch.delenv("MEDAI_PLATFORM_CONTROL_TOKEN", raising=False)
    assert platform_push.push_researcher(tmp_db, "a@x.co") is None


def test_push_puts_the_document_at_the_escaped_path(tmp_db, pushes) -> None:
    u = _user(tmp_db, "ahmed", "a+tag@x.co")
    proj = create_project(tmp_db, name="p", description=None, created_by=u.id)
    pushes.clear()   # creating the project announces itself; this test is about the PUT shape

    assert platform_push.push_researcher(tmp_db, "a+tag@x.co") is True
    assert len(pushes) == 1
    put = pushes[0]
    assert put["method"] == "PUT"
    # The address is a path segment, so every character that means something in
    # a URL is escaped — a '+' that arrived as a space would push the wrong
    # person's entitlements.
    assert put["url"] == "https://platform.example/v1/desired/researchers/a%2Btag%40x.co"
    assert put["body"]["projects"] == [proj.id]
    assert put["body"]["email"] == "a+tag@x.co"


def test_push_survives_every_failure(tmp_db, monkeypatch) -> None:
    _user(tmp_db, "ahmed", "a@x.co")
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_URL", "https://platform.example")
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_TOKEN", "t")

    for boom in (
        HTTPError("u", 409, "conflict", {}, None),
        HTTPError("u", 500, "boom", {}, None),
        URLError("unreachable"),
        TimeoutError("slow"),
    ):
        def _raise(req, timeout=None, context=None, exc=boom):
            raise exc

        monkeypatch.setattr(platform_push.urllib.request, "urlopen", _raise)
        assert platform_push.push_researcher(tmp_db, "a@x.co") is False


def test_push_all_researchers_covers_every_member(tmp_db, pushes) -> None:
    owner = _user(tmp_db, "owner", "o@x.co")
    member = _user(tmp_db, "member", "m@x.co")
    _user(tmp_db, "outsider", "out@x.co")  # in no project: never pushed
    proj = create_project(tmp_db, name="p", description=None, created_by=owner.id)
    add_member(tmp_db, project_id=proj.id, user_id=member.id, role="editor")

    pushes.clear()   # the setup above announced its own project and members
    pushed, failed = platform_push.push_all_researchers(tmp_db)
    assert (pushed, failed) == (2, 0)
    memberships = [p for p in pushes if "/desired/researchers/" in p["url"]]
    assert sorted(p["body"]["email"] for p in memberships) == ["m@x.co", "o@x.co"]


# ── the routes that must fire it ─────────────────────────────────────────────


def test_creating_a_project_pushes_the_creator(client, tmp_db, admin_token, pushes) -> None:
    from gazzali.crud.users import update_user

    admin = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {admin_token}"}).json()
    update_user(tmp_db, admin["id"], email="admin@x.co")

    resp = client.post(
        "/api/v1/projects",
        json={"name": "P"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    # Two calls: the project's own bucket, then the creator's membership.
    memberships = [p for p in pushes if "/desired/researchers/" in p["url"]]
    assert [p["body"]["email"] for p in memberships] == ["admin@x.co"]
    assert memberships[0]["body"]["projects"] == [resp.json()["id"]]


def test_adding_and_removing_a_member_both_push(client, tmp_db, admin_token, pushes) -> None:
    member = _user(tmp_db, "member", "m@x.co")
    project_id = client.post(
        "/api/v1/projects", json={"name": "P"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["id"]
    pushes.clear()

    add = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member.id, "role": "editor"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert add.status_code == 201
    assert pushes[-1]["body"]["email"] == "m@x.co"
    assert pushes[-1]["body"]["projects"] == [project_id]
    first_generation = pushes[-1]["body"]["generation"]

    rm = client.delete(
        f"/api/v1/projects/{project_id}/members/{member.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rm.status_code == 204
    assert pushes[-1]["body"]["email"] == "m@x.co"
    assert pushes[-1]["body"]["projects"] == []
    # Strictly newer, or platform-control would refuse the revocation.
    assert pushes[-1]["body"]["generation"] > first_generation


def test_archiving_a_project_pushes_every_member(client, tmp_db, admin_token, pushes) -> None:
    member = _user(tmp_db, "member", "m@x.co")
    project_id = client.post(
        "/api/v1/projects", json={"name": "P"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["id"]
    add_member(tmp_db, project_id=project_id, user_id=member.id, role="editor")
    pushes.clear()

    resp = client.put(
        f"/api/v1/projects/{project_id}",
        json={"archive": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "m@x.co" in [p["body"]["email"] for p in pushes]
    for p in pushes:
        assert p["body"]["projects"] == []  # an archived project entitles nobody


def test_deleting_a_user_pushes_an_empty_membership(client, tmp_db, admin_token, pushes) -> None:
    member = _user(tmp_db, "member", "m@x.co")
    project_id = client.post(
        "/api/v1/projects", json={"name": "P"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["id"]
    add_member(tmp_db, project_id=project_id, user_id=member.id, role="editor")
    pushes.clear()

    resp = client.delete(
        f"/api/v1/users/{member.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204
    # The address had to be read BEFORE the delete, or there would be nothing
    # to key the revocation on.
    assert [p["body"]["email"] for p in pushes] == ["m@x.co"]
    assert pushes[-1]["body"]["projects"] == []


def test_a_failing_push_never_fails_the_governance_write(
    client, tmp_db, admin_token, monkeypatch
) -> None:
    member = _user(tmp_db, "member", "m@x.co")
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_URL", "https://platform.example")
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_TOKEN", "t")

    def _raise(req, timeout=None, context=None):
        raise URLError("the cluster is down")

    monkeypatch.setattr(platform_push.urllib.request, "urlopen", _raise)

    project_id = client.post(
        "/api/v1/projects", json={"name": "P"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["id"]
    add = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member.id, "role": "editor"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert add.status_code == 201
    rm = client.delete(
        f"/api/v1/projects/{project_id}/members/{member.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rm.status_code == 204


# ── the project's own bucket ────────────────────────────────────────────────


def test_creating_a_project_provisions_its_bucket_before_the_membership(
    client, tmp_db, admin_token, pushes
) -> None:
    from gazzali.crud.users import update_user

    admin = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {admin_token}"}
    ).json()
    update_user(tmp_db, admin["id"], email="admin@x.co")

    resp = client.post(
        "/api/v1/projects",
        json={"name": "Team"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    # Order matters: a membership naming a bucket that does not exist yet
    # entitles nothing, so the dataspace has to be ensured first.
    assert pushes[0]["url"].endswith(f"/v1/dataspaces/proj/{project_id}")
    assert pushes[0]["body"] == {"name": "Team"}
    assert pushes[1]["url"].endswith("/v1/desired/researchers/admin%40x.co")


def test_ensure_project_space_is_a_no_op_when_unconfigured(tmp_db, monkeypatch) -> None:
    monkeypatch.delenv("MEDAI_PLATFORM_CONTROL_URL", raising=False)
    monkeypatch.delenv("MEDAI_PLATFORM_CONTROL_TOKEN", raising=False)
    assert platform_push.ensure_project_space(tmp_db, "whatever") is None


def test_ensure_project_space_refuses_an_unknown_project(tmp_db, pushes) -> None:
    assert platform_push.ensure_project_space(tmp_db, "does-not-exist") is False
    assert pushes == []


def test_ensure_all_project_spaces_skips_archived(tmp_db, pushes) -> None:
    from gazzali.crud.projects import update_project

    u = _user(tmp_db, "ahmed", "a@x.co")
    live = create_project(tmp_db, name="live", description=None, created_by=u.id)
    dead = create_project(tmp_db, name="dead", description=None, created_by=u.id)
    update_project(tmp_db, dead.id, archived_at="2026-08-01T00:00:00Z")

    ensured, failed = platform_push.ensure_all_project_spaces(tmp_db)
    assert (ensured, failed) == (1, 0)
    assert pushes[0]["url"].endswith(f"/v1/dataspaces/proj/{live.id}")


def test_a_failing_space_ensure_never_fails_project_creation(
    client, tmp_db, admin_token, monkeypatch
) -> None:
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_URL", "https://platform.example")
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_TOKEN", "t")

    def _raise(req, timeout=None, context=None):
        raise URLError("the cluster is down")

    monkeypatch.setattr(platform_push.urllib.request, "urlopen", _raise)
    resp = client.post(
        "/api/v1/projects",
        json={"name": "P"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201


# ── the bypass this file exists to prevent ──────────────────────────────────
#
# The hooks used to live in the HTTP routes. The AI assistant's pm_create_project tool
# calls crud.create_project directly, so a project created by asking the assistant got
# no bucket and its owner got no membership push — and their notebook could not open a
# cohort granted to that project, with nothing in any log to say why. These tests pin
# the announcements to the CRUD layer, where every caller passes through.


def test_creating_a_project_through_crud_announces_it(tmp_db, pushes) -> None:
    """The assistant's path: no HTTP route involved."""
    owner = _user(tmp_db, "owner", "o@x.co")
    project = create_project(tmp_db, name="Asked the assistant", description=None,
                             created_by=owner.id)

    assert len(pushes) == 2, [p["url"] for p in pushes]
    # The bucket first — a membership naming a bucket that does not exist entitles nothing.
    assert pushes[0]["url"].endswith(f"/v1/dataspaces/proj/{project.id}")
    assert pushes[0]["body"] == {"name": "Asked the assistant"}
    assert pushes[1]["url"].endswith("/v1/desired/researchers/o%40x.co")
    assert pushes[1]["body"]["projects"] == [project.id]


def test_adding_a_member_through_crud_announces_it(tmp_db, pushes) -> None:
    owner = _user(tmp_db, "owner", "o@x.co")
    member = _user(tmp_db, "member", "m@x.co")
    project = create_project(tmp_db, name="P", description=None, created_by=owner.id)
    pushes.clear()

    add_member(tmp_db, project_id=project.id, user_id=member.id, role="editor")
    assert [p["body"]["email"] for p in pushes] == ["m@x.co"]
    assert pushes[-1]["body"]["projects"] == [project.id]


def test_removing_a_member_through_crud_announces_it(tmp_db, pushes) -> None:
    owner = _user(tmp_db, "owner", "o@x.co")
    member = _user(tmp_db, "member", "m@x.co")
    project = create_project(tmp_db, name="P", description=None, created_by=owner.id)
    add_member(tmp_db, project_id=project.id, user_id=member.id, role="editor")
    pushes.clear()

    assert remove_member(tmp_db, project_id=project.id, user_id=member.id) is True
    assert [p["body"]["email"] for p in pushes] == ["m@x.co"]
    assert pushes[-1]["body"]["projects"] == []

    # A removal that removed nothing must not push: it changed no entitlement.
    pushes.clear()
    assert remove_member(tmp_db, project_id=project.id, user_id=member.id) is False
    assert pushes == []


def test_accepting_an_admission_announces_the_new_project(tmp_db, pushes) -> None:
    from gazzali.crud.admissions import accept_admission, create_admission

    reviewer = _user(tmp_db, "reviewer", "r@x.co")
    adm = create_admission(tmp_db, applicant_name="New Student", email="student@x.co",
                           service_areas="imaging", modas_members="none")
    # accept_admission makes the reviewer the new project's owner, so name one.
    from gazzali.db import get_db

    with get_db(tmp_db) as conn:
        conn.execute("UPDATE admissions SET reviewer_id = ? WHERE id = ?", (reviewer.id, adm.id))
    pushes.clear()

    accept_admission(tmp_db, adm.id)
    # accept_admission builds the project and its owner row with raw SQL, so it has to
    # announce for itself — this is the third caller that used to be missed entirely.
    assert len(pushes) == 2, [p["url"] for p in pushes]
    assert "/v1/dataspaces/proj/" in pushes[0]["url"]
    assert pushes[1]["body"]["email"] == "r@x.co"


def test_an_unreachable_cluster_never_breaks_project_creation(tmp_db, monkeypatch) -> None:
    """The whole point of fire-and-forget: crud is on every code path in the app."""
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_URL", "https://platform.example")
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_TOKEN", "t")

    def _raise(req, timeout=None, context=None):
        raise URLError("the cluster is down")

    monkeypatch.setattr(platform_push.urllib.request, "urlopen", _raise)
    owner = _user(tmp_db, "owner", "o@x.co")
    other = _user(tmp_db, "other", "other@x.co")
    project = create_project(tmp_db, name="P", description=None, created_by=owner.id)
    assert project.id  # created regardless
    assert add_member(tmp_db, project_id=project.id, user_id=other.id, role="viewer") is not None
    assert remove_member(tmp_db, project_id=project.id, user_id=other.id) is True


# ── the labels a console needs ──────────────────────────────────────────────
#
# The delivery console showed "15276631b5164734812c267f8229359c" where a cohort title
# belonged and "Lab 93f675e6fb0e470daede790e9ebcdfff" where a lab name belonged, because
# the pushed document carried no human labels at all. These pin them into the push.


def _approved_dataset(tmp_db, owner, lab_name="Musculoskeletal Imaging",
                      project_name="Fracture detection", ds_name="Ankle radiographs 2019-2025"):
    from gazzali.crud.datasets import create_dataset, create_grant, update_dataset
    from gazzali.crud.labs import create_lab

    lab = create_lab(tmp_db, name=lab_name, pi_id=owner.id)
    project = create_project(tmp_db, name=project_name, description=None, created_by=owner.id)
    ds = create_dataset(tmp_db, name=ds_name, purpose="p", lab_id=lab.id,
                        requested_by=owner.id, accession_list=["ACC1"])
    update_dataset(tmp_db, ds.id, status="approved", retention_until="2027-12-31")
    grant = create_grant(tmp_db, ds.id, project.id, granted_by=owner.id)
    return ds, lab, project, grant


def test_the_push_carries_human_labels(tmp_db) -> None:
    owner = _user(tmp_db, "pi", "pi@x.co")
    ds, lab, project, _grant = _approved_dataset(tmp_db, owner)

    doc = platform_push.build_desired_state(tmp_db, ds.id)
    assert doc["dataset"]["name"] == "Ankle radiographs 2019-2025"
    assert doc["dataset"]["lab_name"] == "Musculoskeletal Imaging"
    # The ids are still there — they are what everything is addressed by.
    assert doc["dataset"]["id"] == ds.id
    assert doc["dataset"]["lab_id"] == lab.id
    # A pending grant is not pushed at all, so approve it first.
    from gazzali.crud.datasets import approve_grant, list_grants

    approve_grant(tmp_db, list_grants(tmp_db, ds.id)[0].id, owner.id)
    doc = platform_push.build_desired_state(tmp_db, ds.id)
    assert doc["grants"][0]["project_name"] == "Fracture detection"
    assert doc["grants"][0]["project_id"] == project.id


def test_a_vanished_lab_or_project_is_an_empty_label_not_a_crash(tmp_db) -> None:
    # Every dataset has a lab (the column is NOT NULL), so the case worth defending is a
    # label lookup for something that no longer exists: it must read as "no label", never
    # raise, because a display string must not be able to fail a governance push.
    assert platform_push._lab_name(tmp_db, "does-not-exist") == ""
    assert platform_push._lab_name(tmp_db, None) == ""
    assert platform_push._lab_name(tmp_db, "") == ""
    assert platform_push._project_name(tmp_db, "does-not-exist") == ""
