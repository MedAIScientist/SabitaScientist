"""Tests for the experiment ↔ project-management and experiment ↔ data links.

Covers the two silent failures this work fixed — a phase assignment that the
PATCH route dropped, and an 'abandoned' status the API rejected while the UI
offered it — plus the asset lineage that connects an experiment to the data it
processed and the imaging artefacts it produced.
"""

from __future__ import annotations

import pytest

from EvoScientist.pm.models import (
    EXPERIMENT_ASSET_ROLES,
    EXPERIMENT_ASSET_TYPES,
    EXPERIMENT_STATUSES,
)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _admin(client, tmp_db, username="exp_admin"):
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user

    create_user(
        tmp_db, username=username, password_hash=hash_password("pw"), is_admin=True
    )
    return client.post(
        "/api/v1/auth/login", json={"username": username, "password": "pw"}
    ).json()["token"]


def _project(client, token, name="Imaging study"):
    resp = client.post("/api/v1/projects", json={"name": name}, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _phase(client, token, pid, name="Preprocessing"):
    resp = client.post(
        f"/api/v1/projects/{pid}/phases",
        json={"name": name, "color": "#6366f1", "position": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _experiment(client, token, pid, **body):
    resp = client.post(
        f"/api/v1/projects/{pid}/experiments",
        json={"name": "Denoise cohort", **body},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── The status vocabulary is one list, not three ──────────────────────────────


def test_every_status_in_the_vocabulary_is_accepted(client, tmp_db) -> None:
    """'abandoned' used to be rejected with a 422 although the UI offered it."""
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    exp = _experiment(client, token, pid)

    for status in EXPERIMENT_STATUSES:
        resp = client.patch(
            f"/api/v1/projects/{pid}/experiments/{exp['id']}",
            json={"status": status},
            headers=_auth(token),
        )
        assert resp.status_code == 200, f"{status}: {resp.text}"
        assert resp.json()["status"] == status


def test_create_accepts_every_status(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    for status in EXPERIMENT_STATUSES:
        assert _experiment(client, token, pid, status=status)["status"] == status


def test_unknown_status_is_still_rejected(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    exp = _experiment(client, token, pid)
    assert (
        client.patch(
            f"/api/v1/projects/{pid}/experiments/{exp['id']}",
            json={"status": "nonsense"},
            headers=_auth(token),
        ).status_code
        == 422
    )


def test_db_check_constraint_matches_the_vocabulary(tmp_db) -> None:
    """Guards the invariant models.EXPERIMENT_STATUSES claims to be the source of."""
    import sqlite3

    sql = (
        sqlite3.connect(tmp_db)
        .execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='experiments'"
        )
        .fetchone()[0]
    )
    assert "CHECK(status IN" in sql
    for status in EXPERIMENT_STATUSES:
        assert f"'{status}'" in sql, f"{status} missing from the DB constraint"


# ── Phase assignment actually persists ────────────────────────────────────────


def test_phase_id_can_be_set_at_creation(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    phase = _phase(client, token, pid)

    exp = _experiment(client, token, pid, phase_id=phase)
    assert exp["phase_id"] == phase


def test_phase_id_can_be_set_by_patch(client, tmp_db) -> None:
    """The board's bulk "set phase" and the detail dropdown both rely on this."""
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    phase = _phase(client, token, pid)
    exp = _experiment(client, token, pid)
    assert exp["phase_id"] is None

    resp = client.patch(
        f"/api/v1/projects/{pid}/experiments/{exp['id']}",
        json={"phase_id": phase},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["phase_id"] == phase

    # and it survives a re-read
    fetched = client.get(
        f"/api/v1/projects/{pid}/experiments/{exp['id']}", headers=_auth(token)
    ).json()
    assert fetched["phase_id"] == phase


def test_phase_id_can_be_cleared_by_patch(client, tmp_db) -> None:
    """Sending null must un-assign; omitting the key must leave it alone."""
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    phase = _phase(client, token, pid)
    exp = _experiment(client, token, pid, phase_id=phase)

    # omitting phase_id leaves it untouched
    untouched = client.patch(
        f"/api/v1/projects/{pid}/experiments/{exp['id']}",
        json={"hypothesis": "changed"},
        headers=_auth(token),
    ).json()
    assert untouched["phase_id"] == phase

    cleared = client.patch(
        f"/api/v1/projects/{pid}/experiments/{exp['id']}",
        json={"phase_id": None},
        headers=_auth(token),
    ).json()
    assert cleared["phase_id"] is None


def test_phase_move_is_reflected_in_the_list(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    first = _phase(client, token, pid, "Collection")
    second = _phase(client, token, pid, "Analysis")
    exp = _experiment(client, token, pid, phase_id=first)

    client.patch(
        f"/api/v1/projects/{pid}/experiments/{exp['id']}",
        json={"phase_id": second},
        headers=_auth(token),
    )
    listed = client.get(
        f"/api/v1/projects/{pid}/experiments", headers=_auth(token)
    ).json()
    assert next(e for e in listed if e["id"] == exp["id"])["phase_id"] == second


# ── Asset vocabulary sanity ───────────────────────────────────────────────────


def test_asset_vocabularies_are_stable() -> None:
    """The API patterns and the DB CHECK are generated from these tuples."""
    assert EXPERIMENT_ASSET_TYPES == (
        "dataset",
        "pipeline_run",
        "cvat_project",
        "webknossos_dataset",
        "sandbox",
    )
    assert EXPERIMENT_ASSET_ROLES == ("input", "processing", "output", "reference")


@pytest.mark.parametrize("asset_type", EXPERIMENT_ASSET_TYPES)
def test_every_asset_type_is_expressible(asset_type) -> None:
    import re

    from EvoScientist.pm.api.schemas import EXPERIMENT_ASSET_TYPE_PATTERN

    assert re.match(EXPERIMENT_ASSET_TYPE_PATTERN, asset_type)


# ── Data lineage: linking assets to an experiment ─────────────────────────────


def _cvat(client, token, pid, name="Ankle annotations"):
    resp = client.post(
        f"/api/v1/projects/{pid}/cvat",
        json={"cvat_id": 7, "name": name},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _webknossos(client, token, pid, name="EM volume"):
    resp = client.post(
        f"/api/v1/projects/{pid}/webknossos",
        json={"name": name, "directory_name": "em-volume-1"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _sandbox(client, token, pid, name="analysis box"):
    resp = client.post(
        f"/api/v1/projects/{pid}/sandboxes", json={"name": name}, headers=_auth(token)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _pipeline_run(client, token, pid):
    pipeline = client.post(
        f"/api/v1/projects/{pid}/deid-pipelines",
        json={"name": "DICOM de-id", "pipeline_type": "dicom"},
        headers=_auth(token),
    )
    assert pipeline.status_code == 201, pipeline.text
    pipeline_id = pipeline.json()["id"]
    run = client.post(
        f"/api/v1/projects/{pid}/deid-pipelines/{pipeline_id}/runs",
        json={
            "pipeline_id": pipeline_id,
            "input_location": "s3://in/",
            "output_location": "s3://out/",
        },
        headers=_auth(token),
    )
    assert run.status_code == 201, run.text
    return pipeline_id, run.json()["id"]


def _link(client, token, pid, eid, asset_type, asset_id, role="input", **extra):
    return client.post(
        f"/api/v1/projects/{pid}/experiments/{eid}/assets",
        json={"asset_type": asset_type, "asset_id": asset_id, "role": role, **extra},
        headers=_auth(token),
    )


def test_pipeline_run_can_be_linked_as_processing(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    eid = _experiment(client, token, pid)["id"]
    _, run_id = _pipeline_run(client, token, pid)

    resp = _link(client, token, pid, eid, "pipeline_run", run_id, role="processing")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["asset_type"] == "pipeline_run"
    assert body["role"] == "processing"
    # the label is resolved server-side so the UI needs no per-type knowledge
    assert body["label"] == "DICOM de-id"


def test_lineage_lists_inputs_then_outputs(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    eid = _experiment(client, token, pid)["id"]
    cvat = _cvat(client, token, pid)
    wk = _webknossos(client, token, pid)
    _, run_id = _pipeline_run(client, token, pid)

    _link(client, token, pid, eid, "cvat_project", cvat, role="output")
    _link(client, token, pid, eid, "pipeline_run", run_id, role="processing")
    _link(client, token, pid, eid, "webknossos_dataset", wk, role="reference")

    listed = client.get(
        f"/api/v1/projects/{pid}/experiments/{eid}/assets", headers=_auth(token)
    ).json()
    assert [a["role"] for a in listed] == ["processing", "output", "reference"]
    assert {a["label"] for a in listed} == {
        "Ankle annotations",
        "DICOM de-id",
        "EM volume",
    }


def test_relinking_the_same_asset_updates_the_role(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    eid = _experiment(client, token, pid)["id"]
    cvat = _cvat(client, token, pid)

    _link(client, token, pid, eid, "cvat_project", cvat, role="input")
    _link(client, token, pid, eid, "cvat_project", cvat, role="output")

    listed = client.get(
        f"/api/v1/projects/{pid}/experiments/{eid}/assets", headers=_auth(token)
    ).json()
    assert len(listed) == 1
    assert listed[0]["role"] == "output"


def test_unlink_removes_only_that_link(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    eid = _experiment(client, token, pid)["id"]
    cvat = _cvat(client, token, pid)
    wk = _webknossos(client, token, pid)
    _link(client, token, pid, eid, "cvat_project", cvat)
    _link(client, token, pid, eid, "webknossos_dataset", wk)

    resp = client.delete(
        f"/api/v1/projects/{pid}/experiments/{eid}/assets/cvat_project/{cvat}",
        headers=_auth(token),
    )
    assert resp.status_code == 204
    remaining = client.get(
        f"/api/v1/projects/{pid}/experiments/{eid}/assets", headers=_auth(token)
    ).json()
    assert [a["asset_type"] for a in remaining] == ["webknossos_dataset"]

    # unlinking again is a 404, not a silent success
    again = client.delete(
        f"/api/v1/projects/{pid}/experiments/{eid}/assets/cvat_project/{cvat}",
        headers=_auth(token),
    )
    assert again.status_code == 404


def test_unknown_asset_id_is_404(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    eid = _experiment(client, token, pid)["id"]
    assert _link(client, token, pid, eid, "cvat_project", "nope").status_code == 404


def test_asset_from_another_project_is_rejected(client, tmp_db) -> None:
    """A link must not become a way to reach across projects."""
    token = _admin(client, tmp_db)
    pid = _project(client, token, "Imaging study")
    other = _project(client, token, "Other study")
    eid = _experiment(client, token, pid)["id"]
    foreign_cvat = _cvat(client, token, other)

    resp = _link(client, token, pid, eid, "cvat_project", foreign_cvat)
    assert resp.status_code == 422
    assert "does not belong" in resp.json()["detail"]


def test_invalid_asset_type_and_role_are_rejected(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    eid = _experiment(client, token, pid)["id"]
    assert _link(client, token, pid, eid, "spaceship", "x").status_code == 422
    assert (
        _link(client, token, pid, eid, "sandbox", "x", role="boss").status_code == 422
    )


def test_linked_asset_count_appears_on_the_experiment(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    eid = _experiment(client, token, pid)["id"]
    detail = client.get(
        f"/api/v1/projects/{pid}/experiments/{eid}", headers=_auth(token)
    ).json()
    assert detail["linked_asset_count"] == 0

    _link(client, token, pid, eid, "cvat_project", _cvat(client, token, pid))
    _link(client, token, pid, eid, "sandbox", _sandbox(client, token, pid))

    listed = client.get(
        f"/api/v1/projects/{pid}/experiments", headers=_auth(token)
    ).json()
    assert next(e for e in listed if e["id"] == eid)["linked_asset_count"] == 2


def test_deleting_the_asset_clears_its_links(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    eid = _experiment(client, token, pid)["id"]
    cvat = _cvat(client, token, pid)
    _link(client, token, pid, eid, "cvat_project", cvat)

    assert (
        client.delete(
            f"/api/v1/projects/{pid}/cvat/{cvat}", headers=_auth(token)
        ).status_code
        == 204
    )
    assert (
        client.get(
            f"/api/v1/projects/{pid}/experiments/{eid}/assets", headers=_auth(token)
        ).json()
        == []
    )


def test_deleting_a_pipeline_clears_its_run_links(client, tmp_db) -> None:
    """Runs cascade with the pipeline, so their lineage links must go too."""
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    eid = _experiment(client, token, pid)["id"]
    pipeline_id, run_id = _pipeline_run(client, token, pid)
    _link(client, token, pid, eid, "pipeline_run", run_id, role="processing")

    assert (
        client.delete(
            f"/api/v1/projects/{pid}/deid-pipelines/{pipeline_id}", headers=_auth(token)
        ).status_code
        == 204
    )
    assert (
        client.get(
            f"/api/v1/projects/{pid}/experiments/{eid}/assets", headers=_auth(token)
        ).json()
        == []
    )


def test_deleting_the_experiment_removes_its_links(client, tmp_db) -> None:
    import sqlite3

    token = _admin(client, tmp_db)
    pid = _project(client, token)
    eid = _experiment(client, token, pid)["id"]
    _link(client, token, pid, eid, "cvat_project", _cvat(client, token, pid))

    assert (
        client.delete(
            f"/api/v1/projects/{pid}/experiments/{eid}", headers=_auth(token)
        ).status_code
        == 204
    )
    with sqlite3.connect(tmp_db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM experiment_assets WHERE experiment_id=?", (eid,)
        ).fetchone()[0]
    assert count == 0


def test_viewer_can_read_lineage_but_not_change_it(client, tmp_db) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.projects import add_member
    from EvoScientist.pm.crud.users import create_user

    token = _admin(client, tmp_db)
    pid = _project(client, token)
    eid = _experiment(client, token, pid)["id"]
    cvat = _cvat(client, token, pid)
    _link(client, token, pid, eid, "cvat_project", cvat)

    viewer = create_user(tmp_db, username="viewer", password_hash=hash_password("pw"))
    add_member(tmp_db, pid, viewer.id, "viewer")
    viewer_token = client.post(
        "/api/v1/auth/login", json={"username": "viewer", "password": "pw"}
    ).json()["token"]

    assert (
        client.get(
            f"/api/v1/projects/{pid}/experiments/{eid}/assets",
            headers=_auth(viewer_token),
        ).status_code
        == 200
    )
    assert (
        _link(
            client, viewer_token, pid, eid, "sandbox", _sandbox(client, token, pid)
        ).status_code
        == 403
    )


# ── Dataset links require an approved grant ───────────────────────────────────


def _dataset_fixture(client, tmp_db):
    """A lab/project/IRB scaffold plus an admin-approved imaging dataset."""
    from tests.pm.test_api_datasets import _approved_dataset, _scaffold

    s = _scaffold(client, tmp_db)
    dataset = _approved_dataset(client, s)
    return s, dataset


def test_dataset_needs_an_approved_grant(client, tmp_db) -> None:
    s, dataset = _dataset_fixture(client, tmp_db)
    pid = s["project"]["id"]
    pi_token = s["pi_token"]
    eid = _experiment(client, pi_token, pid)["id"]

    # no grant at all
    no_grant = _link(client, pi_token, pid, eid, "dataset", dataset["id"])
    assert no_grant.status_code == 422
    assert "not granted" in no_grant.json()["detail"]

    # a proposed grant grants nothing until a platform admin approves it
    grant = client.post(
        f"/api/v1/datasets/{dataset['id']}/grants",
        json={"project_id": pid},
        headers=_auth(pi_token),
    )
    assert grant.status_code == 201, grant.text
    grant_id = grant.json()["id"]
    pending = _link(client, pi_token, pid, eid, "dataset", dataset["id"])
    assert pending.status_code == 422

    # once approved, the same link succeeds
    approve = client.post(
        f"/api/v1/datasets/{dataset['id']}/grants/{grant_id}/approve",
        headers=_auth(s["admin_token"]),
    )
    assert approve.status_code == 200, approve.text
    allowed = _link(client, pi_token, pid, eid, "dataset", dataset["id"], role="input")
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["label"] == "DX ayak/bilek 2019-2025"


def test_revoked_grant_blocks_new_links(client, tmp_db) -> None:
    s, dataset = _dataset_fixture(client, tmp_db)
    pid = s["project"]["id"]
    pi_token = s["pi_token"]
    eid = _experiment(client, pi_token, pid)["id"]
    grant = client.post(
        f"/api/v1/datasets/{dataset['id']}/grants",
        json={"project_id": pid},
        headers=_auth(pi_token),
    ).json()
    client.post(
        f"/api/v1/datasets/{dataset['id']}/grants/{grant['id']}/approve",
        headers=_auth(s["admin_token"]),
    )
    client.delete(
        f"/api/v1/datasets/{dataset['id']}/grants/{grant['id']}",
        headers=_auth(s["admin_token"]),
    )
    assert (
        _link(client, pi_token, pid, eid, "dataset", dataset["id"]).status_code == 422
    )


# ── Project-wide pipeline runs (what the lineage picker offers) ───────────────


def test_project_run_list_is_flat_and_scoped(client, tmp_db) -> None:
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    other = _project(client, token, "Other study")
    _, run_id = _pipeline_run(client, token, pid)
    _pipeline_run(client, token, other)

    runs = client.get(
        f"/api/v1/projects/{pid}/deid-pipeline-runs", headers=_auth(token)
    ).json()
    assert [r["id"] for r in runs] == [run_id]
    assert runs[0]["project_id"] == pid


def test_run_list_rejects_a_pipeline_from_another_project(client, tmp_db) -> None:
    """Guards the cross-project read that the per-pipeline route used to allow."""
    token = _admin(client, tmp_db)
    pid = _project(client, token)
    other = _project(client, token, "Other study")
    foreign_pipeline, _ = _pipeline_run(client, token, other)

    resp = client.get(
        f"/api/v1/projects/{pid}/deid-pipelines/{foreign_pipeline}/runs",
        headers=_auth(token),
    )
    assert resp.status_code == 404
