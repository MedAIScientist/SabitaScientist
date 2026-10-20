"""The cohort API: versions, population, flow, trace, replay, analyses and publishing.

The phases of ``plan/cohort-analiz-roadmap.md`` are tested in the order the app makes
a researcher work through them, so a failure points at the step that broke.
"""

from __future__ import annotations

import csv
import io
import json

import numpy as np
import pandas as pd
import pytest

from gazzali import settings
from gazzali.auth import hash_password
from gazzali.crud.experiments import create_experiment
from gazzali.crud.projects import create_project
from gazzali.crud.publications import create_publication
from gazzali.crud.users import create_user
from gazzali.db import get_db


@pytest.fixture
def cohort_root(tmp_path, monkeypatch):
    """Point the version store at a temp directory for the duration of a test."""
    root = tmp_path / "cohort"
    root.mkdir()
    monkeypatch.setattr(settings, "COHORT_DIR", root)
    return root


@pytest.fixture
def owner(tmp_db):
    return create_user(
        tmp_db,
        username="biostat",
        password_hash=hash_password("statpass1"),
        is_admin=False,
    )


@pytest.fixture
def viewer(tmp_db):
    return create_user(
        tmp_db,
        username="reader",
        password_hash=hash_password("readpass1"),
        is_admin=False,
    )


@pytest.fixture
def project(tmp_db, owner):
    return create_project(tmp_db, "Heart failure cohort", owner.id)


@pytest.fixture
def experiment(tmp_db, project, owner):
    return create_experiment(tmp_db, project.id, "Baseline table", owner.id)


@pytest.fixture
def headers(client, owner):
    """A signed-in owner. Depends on ``owner`` so the account exists before the login."""
    token = client.post(
        "/api/v1/auth/login", json={"username": "biostat", "password": "statpass1"}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cohort_csv() -> bytes:
    rng = np.random.default_rng(3)
    n = 160
    frame = pd.DataFrame(
        {
            "age": rng.normal(61, 10, n).round(),
            "sex": rng.choice(["Female", "Male"], n),
            "nyha": rng.choice(["II", "III", "IV"], n),
            "lvef": rng.normal(48, 12, n).round(1),
            "weight_kg": rng.normal(78, 12, n).round(1),
            "height_cm": rng.normal(168, 8, n).round(1),
        }
    )
    frame.loc[0, "age"] = 250.0  # fails the plausibility criterion
    frame.loc[rng.choice(n, 8, replace=False), "lvef"] = np.nan
    return frame.to_csv(index=False).encode()


def _url(project_id: str, suffix: str = "") -> str:
    return f"/api/v1/projects/{project_id}/cohort{suffix}"


def _make_table(
    client, headers, project_id: str, name: str = "tutorial", **extra
) -> dict:
    response = client.post(
        _url(project_id, "/tables"),
        json={"name": name, "data_origin": "public", **extra},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload(client, headers, project_id: str, table_id: str, content: bytes) -> dict:
    response = client.post(
        _url(project_id, f"/tables/{table_id}/versions"),
        files={"file": ("cohort.csv", content, "text/csv")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


CONFIG = {
    "mask_families": {
        "inclusion": {
            "operator": "all",
            "plausible_age": {
                "numeric": True,
                "column": "age",
                "lower_bound": 18,
                "upper_bound": 110,
            },
        },
        "anomalies": {"operator": "any", "lvef_range": {"bounds": {"lvef": [5, 90]}}},
    }
}


# ---------------------------------------------------------------------------
# phase 1: table, version, population, flow
# ---------------------------------------------------------------------------


def test_create_list_and_get_a_table(client, headers, project, cohort_root):
    table = _make_table(client, headers, project.id)
    listed = client.get(_url(project.id, "/tables"), headers=headers).json()
    assert [item["id"] for item in listed] == [table["id"]]
    fetched = client.get(
        _url(project.id, f"/tables/{table['id']}"), headers=headers
    ).json()
    assert fetched["data_origin"] == "public"
    assert fetched["versions"] == []


def test_a_table_name_is_unique_within_a_project(client, headers, project, cohort_root):
    _make_table(client, headers, project.id)
    duplicate = client.post(
        _url(project.id, "/tables"),
        json={"name": "tutorial", "data_origin": "public"},
        headers=headers,
    )
    assert duplicate.status_code == 409


def test_a_governed_cohort_cannot_be_created_without_a_dataset(
    client, headers, project, cohort_root
):
    response = client.post(
        _url(project.id, "/tables"),
        json={"name": "patients", "data_origin": "governed"},
        headers=headers,
    )
    assert response.status_code == 409
    assert "dataset" in response.json()["detail"]


def test_a_public_cohort_cannot_name_a_dataset(client, headers, project, cohort_root):
    response = client.post(
        _url(project.id, "/tables"),
        json={"name": "x", "data_origin": "public", "dataset_id": "abc"},
        headers=headers,
    )
    assert response.status_code == 409


def test_upload_creates_a_version_and_a_baseline_population(
    client, headers, project, cohort_root, cohort_csv
):
    table = _make_table(client, headers, project.id)
    version = _upload(client, headers, project.id, table["id"], cohort_csv)
    assert version["version_no"] == 1
    assert version["rows"] == 160
    assert version["parse_report"]["delimiter"] == ","
    refreshed = client.get(
        _url(project.id, f"/tables/{table['id']}"), headers=headers
    ).json()
    assert refreshed["active_population"]["name"] == "All rows (no criteria)"
    assert refreshed["active_population"]["n_included"] == 160


def test_upload_rejects_an_unsupported_file(client, headers, project, cohort_root):
    table = _make_table(client, headers, project.id)
    response = client.post(
        _url(project.id, f"/tables/{table['id']}/versions"),
        files={"file": ("notes.txtx", b"a,b", "text/plain")},
        headers=headers,
    )
    assert response.status_code == 422


def test_population_evaluates_the_ticked_criteria(
    client, headers, project, cohort_root, cohort_csv
):
    table = _make_table(client, headers, project.id)
    _upload(client, headers, project.id, table["id"], cohort_csv)
    client.patch(
        _url(project.id, f"/tables/{table['id']}"),
        json={"config": CONFIG},
        headers=headers,
    )

    criteria = client.get(
        _url(project.id, f"/tables/{table['id']}/criteria"), headers=headers
    ).json()
    assert {item["id"] for item in criteria} == {
        "inclusion::plausible_age",
        "anomalies::lvef_range",
    }

    response = client.post(
        _url(project.id, f"/tables/{table['id']}/populations"),
        json={
            "name": "Adults with a plausible LVEF",
            "criteria": ["inclusion::plausible_age"],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    population = response.json()
    assert population["n_base"] == 160
    assert population["n_included"] == 159  # the implausible age is excluded
    assert population["fingerprint"]


def test_population_rejects_an_unknown_criterion(
    client, headers, project, cohort_root, cohort_csv
):
    table = _make_table(client, headers, project.id)
    _upload(client, headers, project.id, table["id"], cohort_csv)
    response = client.post(
        _url(project.id, f"/tables/{table['id']}/populations"),
        json={"name": "x", "criteria": ["inclusion::nope"]},
        headers=headers,
    )
    assert response.status_code == 422


def test_participant_flow_adds_up(client, headers, project, cohort_root, cohort_csv):
    table = _make_table(client, headers, project.id)
    _upload(client, headers, project.id, table["id"], cohort_csv)
    client.patch(
        _url(project.id, f"/tables/{table['id']}"),
        json={"config": CONFIG},
        headers=headers,
    )
    population = client.post(
        _url(project.id, f"/tables/{table['id']}/populations"),
        json={"name": "Adults", "criteria": ["inclusion::plausible_age"]},
        headers=headers,
    ).json()

    flow = client.get(
        _url(project.id, f"/tables/{table['id']}/populations/{population['id']}/flow"),
        headers=headers,
    ).json()
    assert flow["inconsistencies"] == []
    labels = [box["label"] for box in flow["main"]]
    assert any("Records read" in label for label in labels)
    assert flow["main"][-1]["n"] == population["n_included"]
    excluded = sum(item["n"] for item in flow["exits"])
    assert flow["main"][-1]["n"] == flow["main"][0]["n"] - excluded


# ---------------------------------------------------------------------------
# phase 2: quality, trace, replay
# ---------------------------------------------------------------------------


def test_quality_scorecard_is_served_for_a_version(
    client, headers, project, cohort_root, cohort_csv
):
    table = _make_table(client, headers, project.id)
    version = _upload(client, headers, project.id, table["id"], cohort_csv)
    report = client.get(
        _url(project.id, f"/tables/{table['id']}/versions/{version['id']}/quality"),
        headers=headers,
    ).json()
    assert 0.0 <= report["score"] <= 1.0
    assert report["band"] in {"excellent", "good", "fair", "poor"}
    assert len(report["dimensions"]) == 5


def test_derive_writes_a_new_version_and_keeps_the_old_one(
    client, headers, project, cohort_root, cohort_csv
):
    table = _make_table(client, headers, project.id)
    version = _upload(client, headers, project.id, table["id"], cohort_csv)
    response = client.post(
        _url(project.id, f"/tables/{table['id']}/versions/{version['id']}/derive"),
        json={
            "name": "bmi",
            "expression": "df['weight_kg'] / (df['height_cm']/100)**2",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    derived = response.json()
    assert derived["version_no"] == 2
    assert derived["parent_version_id"] == version["id"]
    assert any(column["name"] == "bmi" for column in derived["columns_meta"])
    versions = client.get(
        _url(project.id, f"/tables/{table['id']}/versions"), headers=headers
    ).json()
    assert {item["version_no"] for item in versions} == {1, 2}


def test_derive_rejects_an_unsafe_expression(
    client, headers, project, cohort_root, cohort_csv
):
    table = _make_table(client, headers, project.id)
    version = _upload(client, headers, project.id, table["id"], cohort_csv)
    response = client.post(
        _url(project.id, f"/tables/{table['id']}/versions/{version['id']}/derive"),
        json={"name": "bad", "expression": "open('/etc/passwd').read()"},
        headers=headers,
    )
    assert response.status_code == 422


def test_filter_writes_a_new_version(client, headers, project, cohort_root, cohort_csv):
    table = _make_table(client, headers, project.id)
    version = _upload(client, headers, project.id, table["id"], cohort_csv)
    response = client.post(
        _url(project.id, f"/tables/{table['id']}/versions/{version['id']}/filter"),
        json={"action": "drop", "row_ids": [[0, 9]]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["rows"] == 150


def test_trace_is_chained_and_verified(
    client, headers, project, cohort_root, cohort_csv
):
    table = _make_table(client, headers, project.id)
    version = _upload(client, headers, project.id, table["id"], cohort_csv)
    client.post(
        _url(project.id, f"/tables/{table['id']}/versions/{version['id']}/derive"),
        json={
            "name": "bmi",
            "expression": "df['weight_kg'] / (df['height_cm']/100)**2",
        },
        headers=headers,
    )
    trace = client.get(
        _url(project.id, f"/tables/{table['id']}/trace"), headers=headers
    ).json()
    assert [step["kind"] for step in trace["steps"]] == ["import", "derive"]
    assert trace["chain"]["verified"] is True
    assert trace["chain"]["head"] == trace["steps"][-1]["hash"]


def test_a_hand_edited_step_is_reported_as_tampering(
    client, headers, project, cohort_root, cohort_csv, tmp_db
):
    table = _make_table(client, headers, project.id)
    _upload(client, headers, project.id, table["id"], cohort_csv)
    with get_db(tmp_db) as conn:
        conn.execute(
            "UPDATE cohort_steps SET params_json = ? WHERE table_id = ? AND kind = 'import'",
            (json.dumps({"filename": "forged.csv"}), table["id"]),
        )
    trace = client.get(
        _url(project.id, f"/tables/{table['id']}/trace"), headers=headers
    ).json()
    assert trace["chain"]["verified"] is False
    assert any(
        "does not match its hash" in problem for problem in trace["chain"]["problems"]
    )


def test_replay_reconciles_every_step(
    client, headers, project, cohort_root, cohort_csv
):
    table = _make_table(client, headers, project.id)
    version = _upload(client, headers, project.id, table["id"], cohort_csv)
    client.post(
        _url(project.id, f"/tables/{table['id']}/versions/{version['id']}/derive"),
        json={
            "name": "bmi",
            "expression": "df['weight_kg'] / (df['height_cm']/100)**2",
        },
        headers=headers,
    )
    response = client.post(
        _url(project.id, f"/tables/{table['id']}/replay"), headers=headers
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["reconciled"] is True, payload["problems"]
    assert all(step["status"] == "verified" for step in payload["steps"])


def test_replay_names_the_step_that_no_longer_reproduces(
    client, headers, project, cohort_root, cohort_csv, tmp_db
):
    """A version whose file changed after it was written must not replay as verified."""
    table = _make_table(client, headers, project.id)
    version = _upload(client, headers, project.id, table["id"], cohort_csv)
    derived = client.post(
        _url(project.id, f"/tables/{table['id']}/versions/{version['id']}/derive"),
        json={
            "name": "bmi",
            "expression": "df['weight_kg'] / (df['height_cm']/100)**2",
        },
        headers=headers,
    ).json()
    # Rewrite the derived version's file with different values, keeping its row count.
    from gazzali.cohort import store

    path = cohort_root / store.version_rel_path(table["id"], derived["version_no"])
    frame = pd.read_parquet(path)
    frame["bmi"] = 0.0
    frame.to_parquet(path, index=True)

    response = client.post(
        _url(project.id, f"/tables/{table['id']}/replay"), headers=headers
    )
    payload = response.json()
    assert payload["reconciled"] is False
    assert any(step["status"] in {"differs", "failed"} for step in payload["steps"])


# ---------------------------------------------------------------------------
# phase 3: analyses
# ---------------------------------------------------------------------------


@pytest.fixture
def analysed(client, headers, project, cohort_root, cohort_csv):
    """A table with data, a configuration, and an 'Adults' population."""
    table = _make_table(client, headers, project.id)
    version = _upload(client, headers, project.id, table["id"], cohort_csv)
    client.patch(
        _url(project.id, f"/tables/{table['id']}"),
        json={"config": CONFIG},
        headers=headers,
    )
    population = client.post(
        _url(project.id, f"/tables/{table['id']}/populations"),
        json={"name": "Adults", "criteria": ["inclusion::plausible_age"]},
        headers=headers,
    ).json()
    return {"table": table, "version": version, "population": population}


def test_descriptive_analysis_is_stored_with_its_provenance(
    client, headers, project, analysed
):
    table, population = analysed["table"], analysed["population"]
    response = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "descriptive", "variables": ["age", "sex"]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    analysis = response.json()
    assert analysis["status"] == "current"
    assert analysis["population_fingerprint"] == population["fingerprint"]
    assert analysis["n"] == population["n_included"]
    assert [value["name"] for value in analysis["values"]]


def test_table_one_has_groups_and_adjusted_p_values(client, headers, project, analysed):
    table, population = analysed["table"], analysed["population"]
    response = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "table1", "variables": ["age", "lvef", "sex"], "group": "nyha"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    rendered = response.json()["table"]
    assert rendered["columns"][-1]["key"] == "p"
    age_row = rendered["rows"][0]
    assert age_row["p"] is not None
    assert age_row["p_adjusted"] >= age_row["p"] - 1e-12


def test_compare_reports_the_estimate_with_its_interval(
    client, headers, project, analysed
):
    table, population = analysed["table"], analysed["population"]
    response = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "compare", "outcome": "lvef", "group": "sex", "kind": "welch"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    analysis = response.json()
    assert analysis["result"]["estimate"] is not None
    assert analysis["result"]["effect_sizes"]
    assert analysis["result"]["assumptions"]


def test_an_unknown_method_is_refused(client, headers, project, analysed):
    table, population = analysed["table"], analysed["population"]
    response = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "cox", "variables": ["age"]},
        headers=headers,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# phase 4: staleness and the metrics bridge
# ---------------------------------------------------------------------------


def test_a_new_population_makes_the_previous_analyses_stale(
    client, headers, project, analysed
):
    table, population = analysed["table"], analysed["population"]
    analysis = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "descriptive", "variables": ["age"]},
        headers=headers,
    ).json()
    assert analysis["status"] == "current"

    client.post(
        _url(project.id, f"/tables/{table['id']}/populations"),
        json={"name": "Narrower cohort", "criteria": ["anomalies::lvef_range"]},
        headers=headers,
    )
    reread = client.get(
        _url(project.id, f"/tables/{table['id']}/analyses/{analysis['id']}"),
        headers=headers,
    ).json()
    assert reread["status"] == "stale"
    assert "superseded" in reread["stale_reason"]


def test_publishing_writes_metrics_that_verify_numbers_accepts(
    client, headers, project, experiment, analysed, tmp_db
):
    from gazzali.verify_numbers import recorded_values

    table, population = analysed["table"], analysed["population"]
    analysis = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "compare", "outcome": "lvef", "group": "sex"},
        headers=headers,
    ).json()
    expected = next(
        value for value in analysis["values"] if value["name"] == "lvef:estimate"
    )

    publication = create_publication(
        tmp_db, "A cohort paper", analysed["table"]["created_by"], project_id=project.id
    )
    response = client.post(
        _url(project.id, f"/tables/{table['id']}/analyses/{analysis['id']}/publish"),
        json={"experiment_id": experiment.id, "names": ["lvef:estimate"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["published"][0]["name"] == "lvef:estimate"

    recorded = recorded_values(tmp_db, publication.id)
    assert any(abs(value - expected["value"]) < 1e-9 for value in recorded)

    with get_db(tmp_db) as conn:
        row = conn.execute(
            "SELECT source, source_analysis_id FROM experiment_metrics WHERE source_analysis_id IS NOT NULL"
        ).fetchone()
    assert row["source"] == f"cohort:{analysis['id']}"
    assert row["source_analysis_id"] == analysis["id"]


def test_a_stale_analysis_cannot_be_published_and_stops_verifying(
    client, headers, project, experiment, analysed, tmp_db
):
    from gazzali.verify_numbers import recorded_values

    table, population = analysed["table"], analysed["population"]
    analysis = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "compare", "outcome": "lvef", "group": "sex"},
        headers=headers,
    ).json()
    publication = create_publication(
        tmp_db, "A cohort paper", analysed["table"]["created_by"], project_id=project.id
    )
    first = client.post(
        _url(project.id, f"/tables/{table['id']}/analyses/{analysis['id']}/publish"),
        json={"experiment_id": experiment.id, "names": ["lvef:estimate"]},
        headers=headers,
    )
    assert first.status_code == 200
    assert recorded_values(tmp_db, publication.id)

    # The study's population moves on: the published number is no longer the answer.
    client.post(
        _url(project.id, f"/tables/{table['id']}/populations"),
        json={"name": "Narrower cohort", "criteria": ["anomalies::lvef_range"]},
        headers=headers,
    )
    assert recorded_values(tmp_db, publication.id) == []

    refused = client.post(
        _url(project.id, f"/tables/{table['id']}/analyses/{analysis['id']}/publish"),
        json={"experiment_id": experiment.id, "names": ["lvef:estimate"]},
        headers=headers,
    )
    assert refused.status_code == 409
    assert "stale" in refused.json()["detail"]


def test_publishing_to_an_experiment_of_another_project_is_refused(
    client, headers, project, analysed, tmp_db, owner
):
    other = create_project(tmp_db, "Another project", owner.id)
    foreign = create_experiment(tmp_db, other.id, "not mine", owner.id)
    table, population = analysed["table"], analysed["population"]
    analysis = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "descriptive", "variables": ["age"]},
        headers=headers,
    ).json()
    response = client.post(
        _url(project.id, f"/tables/{table['id']}/analyses/{analysis['id']}/publish"),
        json={"experiment_id": foreign.id},
        headers=headers,
    )
    assert response.status_code == 404


def test_export_returns_csv_with_the_fingerprint(client, headers, project, analysed):
    table, population = analysed["table"], analysed["population"]
    analysis = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "table1", "variables": ["age"], "group": "nyha"},
        headers=headers,
    ).json()
    response = client.get(
        _url(project.id, f"/tables/{table['id']}/analyses/{analysis['id']}/export"),
        headers=headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert population["fingerprint"] in response.text


# ---------------------------------------------------------------------------
# access control
# ---------------------------------------------------------------------------


def test_a_viewer_cannot_upload_a_version(
    client, headers, project, cohort_root, tmp_db, viewer
):
    from gazzali.crud.projects import add_member

    add_member(tmp_db, project.id, viewer.id, "viewer")
    table = _make_table(client, headers, project.id)
    viewer_token = client.post(
        "/api/v1/auth/login", json={"username": "reader", "password": "readpass1"}
    ).json()["token"]
    response = client.post(
        _url(project.id, f"/tables/{table['id']}/versions"),
        files={"file": ("c.csv", b"a,b\n1,2\n", "text/csv")},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


def test_a_non_member_sees_nothing(
    client, headers, project, cohort_root, tmp_db, viewer
):
    table = _make_table(client, headers, project.id)
    viewer_token = client.post(
        "/api/v1/auth/login", json={"username": "reader", "password": "readpass1"}
    ).json()["token"]
    response = client.get(
        _url(project.id, f"/tables/{table['id']}"),
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 404


def test_deleting_a_table_removes_its_files(
    client, headers, project, cohort_root, cohort_csv
):
    table = _make_table(client, headers, project.id)
    _upload(client, headers, project.id, table["id"], cohort_csv)
    assert any(cohort_root.iterdir())
    response = client.delete(
        _url(project.id, f"/tables/{table['id']}"), headers=headers
    )
    assert response.status_code == 204
    assert not any(cohort_root.iterdir())


# ---------------------------------------------------------------------------
# phase 5: survival, Cox, diagnostic accuracy, 2x2 association
# ---------------------------------------------------------------------------


@pytest.fixture
def followup_csv() -> bytes:
    """A cohort with a follow-up time, an event indicator and a binary exposure."""
    rng = np.random.default_rng(31)
    n = 200
    frame = pd.DataFrame(
        {
            "age": rng.normal(62, 9, n).round(),
            "months": rng.exponential(24, n).round(1),
            "died": rng.choice(["yes", "no"], n, p=[0.55, 0.45]),
            "arm": rng.choice(["control", "treatment"], n),
            "score": rng.normal(50, 12, n).round(1),
            "exposed": rng.choice(["exposed", "unexposed"], n),
        }
    )
    # Make the score separate the outcome so the AUC is not a coin flip.
    frame.loc[frame["died"] == "yes", "score"] += 12
    return frame.to_csv(index=False).encode()


@pytest.fixture
def followup(client, headers, project, cohort_root, followup_csv):
    """A table with follow-up data and an 'Adults' population on it."""
    table = _make_table(client, headers, project.id, name="follow-up")
    _upload(client, headers, project.id, table["id"], followup_csv)
    client.patch(
        _url(project.id, f"/tables/{table['id']}"),
        json={"config": CONFIG},
        headers=headers,
    )
    population = client.post(
        _url(project.id, f"/tables/{table['id']}/populations"),
        json={"name": "Adults", "criteria": ["inclusion::plausible_age"]},
        headers=headers,
    ).json()
    return {"table": table, "population": population}


def _run(client, headers, project_id, fixture, body):
    return client.post(
        _url(
            project_id,
            f"/tables/{fixture['table']['id']}/populations/{fixture['population']['id']}/analyses",
        ),
        json=body,
        headers=headers,
    )


def test_survival_analysis_over_the_api(client, headers, project, followup):
    response = _run(
        client,
        headers,
        project.id,
        followup,
        {"method": "survival", "time": "months", "event": "died", "group": "arm"},
    )
    assert response.status_code == 201, response.text
    analysis = response.json()
    assert analysis["status"] == "current"
    assert analysis["result"]["logrank"]["p_value"] is not None
    assert len(analysis["result"]["curves"]) == 2
    assert any(
        "log-rank" in (note or "").lower() for note in analysis["table"]["notes"]
    )
    names = {value["name"] for value in analysis["values"]}
    assert "months:logrank_p" in names


def test_cox_analysis_over_the_api(client, headers, project, followup):
    response = _run(
        client,
        headers,
        project.id,
        followup,
        {
            "method": "cox",
            "time": "months",
            "event": "died",
            "covariates": ["arm", "age"],
        },
    )
    assert response.status_code == 201, response.text
    analysis = response.json()
    terms = analysis["result"]["terms"]
    assert [term["term"] for term in terms] == ["arm_treatment", "age"]
    assert all(term["hr"] > 0 for term in terms)
    assert any(value["name"] == "cox:arm_treatment:hr" for value in analysis["values"])


def test_diagnostic_analysis_over_the_api(client, headers, project, followup):
    response = _run(
        client,
        headers,
        project.id,
        followup,
        {"method": "diagnostic", "test": "score", "outcome": "died", "cutoff": 55},
    )
    assert response.status_code == 201, response.text
    analysis = response.json()
    assert 0.5 < analysis["result"]["auc"]["estimate"] <= 1.0
    assert analysis["result"]["cutoff"] == 55
    names = {value["name"] for value in analysis["values"]}
    assert {"score:auc", "score:sensitivity", "score:specificity"} <= names


def test_2x2_analysis_over_the_api(client, headers, project, followup):
    response = _run(
        client,
        headers,
        project.id,
        followup,
        {"method": "ratio2x2", "exposure": "exposed", "outcome": "died"},
    )
    assert response.status_code == 201, response.text
    result = response.json()["result"]
    assert result["odds_ratio"] > 0
    assert result["relative_risk"] > 0
    assert result["exposure_level"] == "exposed"


def test_a_survival_value_can_be_published_like_any_other(
    client, headers, project, experiment, followup
):
    analysis = _run(
        client,
        headers,
        project.id,
        followup,
        {"method": "survival", "time": "months", "event": "died", "group": "arm"},
    ).json()
    response = client.post(
        _url(
            project.id,
            f"/tables/{followup['table']['id']}/analyses/{analysis['id']}/publish",
        ),
        json={"experiment_id": experiment.id, "names": ["months:logrank_p"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["published"][0]["name"] == "months:logrank_p"


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"method": "cox", "time": "months", "event": "died"}, "covariate"),
        (
            {"method": "survival", "time": "months", "event": "died", "group": "nope"},
            "grouping",
        ),
        (
            {"method": "ratio2x2", "exposure": "arm", "outcome": "arm"},
            "different columns",
        ),
        ({"method": "diagnostic", "test": "arm", "outcome": "died"}, "not numeric"),
    ],
)
def test_an_unusable_parameter_is_refused(
    client, headers, project, followup, body, detail
):
    response = _run(client, headers, project.id, followup, body)
    assert response.status_code == 422, response.text
    assert detail in response.json()["detail"].lower()


def test_a_2x2_needs_two_levels_on_both_sides(client, headers, project, analysed):
    """NYHA has three classes: it is not an exposure you can put in a 2x2 table."""
    table, population = analysed["table"], analysed["population"]
    response = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "ratio2x2", "exposure": "nyha", "outcome": "sex"},
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert "two levels" in response.json()["detail"].lower()


def test_logistic_analysis_over_the_api(client, headers, project, followup):
    response = _run(
        client,
        headers,
        project.id,
        followup,
        {"method": "logistic", "outcome": "died", "covariates": ["arm", "score"]},
    )
    assert response.status_code == 201, response.text
    analysis = response.json()
    assert [term["term"] for term in analysis["result"]["terms"]] == [
        "arm_treatment",
        "score",
    ]
    assert analysis["result"]["terms"][0]["or"] > 0
    assert any(
        value["name"] == "logistic:arm_treatment:or" for value in analysis["values"]
    )


def test_mantel_haenszel_analysis_over_the_api(client, headers, project, followup):
    response = _run(
        client,
        headers,
        project.id,
        followup,
        {
            "method": "mantel_haenszel",
            "exposure": "exposed",
            "outcome": "died",
            "stratum": "arm",
        },
    )
    assert response.status_code == 201, response.text
    analysis = response.json()
    assert analysis["result"]["n_strata"] == 2
    assert analysis["result"]["or_mh"] > 0
    assert any("compared with" in note for note in analysis["table"]["notes"])


def test_agreement_over_the_api(client, headers, project, followup):
    response = _run(
        client,
        headers,
        project.id,
        followup,
        {"method": "agreement", "raters": ["score", "age"], "measure": "bland_altman"},
    )
    assert response.status_code == 201, response.text
    analysis = response.json()
    assert analysis["result"]["measure"] == "bland_altman"
    assert any(value["name"] == "agreement:bias" for value in analysis["values"])


def test_export_writes_a_header_that_matches_every_row(
    client, headers, project, analysed
):
    """A CSV whose rows are longer than its header is silently unreadable in Excel."""
    table, population = analysed["table"], analysed["population"]
    analysis = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "table1", "variables": ["age", "sex"], "group": "nyha"},
        headers=headers,
    ).json()
    response = client.get(
        _url(project.id, f"/tables/{table['id']}/analyses/{analysis['id']}/export"),
        headers=headers,
    )
    assert response.status_code == 200
    rows = [
        line for line in response.text.splitlines() if line and not line.startswith("#")
    ]
    header = next(csv.reader([rows[0]]))
    data = [next(csv.reader([line])) for line in rows[1:] if line.strip()]
    assert header[0] == "Variable"
    assert data
    assert {len(row) for row in data} == {len(header)}


# ---------------------------------------------------------------------------
# phase 6: missing data over the API
# ---------------------------------------------------------------------------


@pytest.fixture
def missing_csv() -> bytes:
    """A cohort with LVEF missing, more often in the sickest class."""
    rng = np.random.default_rng(37)
    n = 180
    frame = pd.DataFrame(
        {
            "age": rng.normal(62, 9, n).round(),
            "lvef": rng.normal(48, 12, n).round(1),
            "nyha": rng.choice(["II", "III", "IV"], n),
            "arm": rng.choice(["control", "treatment"], n),
        }
    )
    frame["lvef"] += frame["nyha"].map({"II": 4.0, "III": 0.0, "IV": -6.0})
    deleted = rng.random(n) < np.where(frame["nyha"] == "IV", 0.5, 0.12)
    frame.loc[deleted, "lvef"] = np.nan
    return frame.to_csv(index=False).encode()


@pytest.fixture
def missing(client, headers, project, cohort_root, missing_csv):
    table = _make_table(client, headers, project.id, name="with-missing")
    _upload(client, headers, project.id, table["id"], missing_csv)
    client.patch(
        _url(project.id, f"/tables/{table['id']}"),
        json={"config": CONFIG},
        headers=headers,
    )
    population = client.post(
        _url(project.id, f"/tables/{table['id']}/populations"),
        json={"name": "Adults", "criteria": ["inclusion::plausible_age"]},
        headers=headers,
    ).json()
    return {"table": table, "population": population}


def test_mcar_analysis_over_the_api(client, headers, project, missing):
    response = _run(
        client,
        headers,
        project.id,
        missing,
        {"method": "mcar", "variables": ["age", "lvef"]},
    )
    assert response.status_code == 201, response.text
    analysis = response.json()
    assert analysis["result"]["df"] >= 1
    assert 0.0 <= analysis["result"]["p_value"] <= 1.0
    assert any("does not prove" in note for note in analysis["table"]["notes"])


def test_multiple_imputation_over_the_api(client, headers, project, missing):
    response = _run(
        client,
        headers,
        project.id,
        missing,
        {
            "method": "multiple_imputation",
            "target": "compare",
            "outcome": "lvef",
            "group": "arm",
            "m": 3,
            "maxit": 3,
            "seed": 42,
        },
    )
    assert response.status_code == 201, response.text
    analysis = response.json()
    assert analysis["result"]["m"] == 3
    assert analysis["result"]["imputed"]["lvef"] > 0
    assert analysis["values"], "the pooled estimate must be publishable"
    assert any(
        column["key"] == "cc_estimate" for column in analysis["table"]["columns"]
    )


def test_a_pooled_estimate_can_be_published(
    client, headers, project, experiment, missing
):
    analysis = _run(
        client,
        headers,
        project.id,
        missing,
        {
            "method": "multiple_imputation",
            "target": "compare",
            "outcome": "lvef",
            "group": "arm",
            "m": 3,
            "maxit": 3,
            "seed": 42,
        },
    ).json()
    response = client.post(
        _url(
            project.id,
            f"/tables/{missing['table']['id']}/analyses/{analysis['id']}/publish",
        ),
        json={"experiment_id": experiment.id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["published"]


def test_imputation_with_nothing_missing_is_refused(client, headers, project, followup):
    """The follow-up cohort is complete: MI there would be a no-op dressed up as an analysis."""
    response = _run(
        client,
        headers,
        project.id,
        followup,
        {
            "method": "multiple_imputation",
            "target": "compare",
            "outcome": "score",
            "group": "arm",
        },
    )
    assert response.status_code == 422, response.text
    assert "nothing to impute" in response.json()["detail"]


# ---------------------------------------------------------------------------
# phase 7: the study dossier
# ---------------------------------------------------------------------------


def _dossier_text(payload: bytes) -> str:
    from docx import Document

    read = Document(io.BytesIO(payload))
    parts = [paragraph.text for paragraph in read.paragraphs]
    for table in read.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def test_the_dossier_downloads_as_a_word_document(client, headers, project, analysed):
    table, population = analysed["table"], analysed["population"]
    client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "table1", "variables": ["age", "lvef"], "group": "nyha"},
        headers=headers,
    )
    response = client.get(
        _url(project.id, f"/tables/{table['id']}/dossier"), headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert ".docx" in response.headers["content-disposition"]
    text = _dossier_text(response.content)
    # The three things a dossier is for: provenance, the flow, the disclaimer.
    assert population["fingerprint"] in text
    assert "Participant flow" in text
    assert "not a compliance certificate" in text


def test_the_dossier_carries_a_selected_result(client, headers, project, analysed):
    table, population = analysed["table"], analysed["population"]
    analysis = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "compare", "outcome": "lvef", "group": "sex"},
        headers=headers,
    ).json()
    response = client.get(
        _url(project.id, f"/tables/{table['id']}/dossier"),
        params={"analysis_id": analysis["id"]},
        headers=headers,
    )
    assert response.status_code == 200
    text = _dossier_text(response.content)
    assert "5.1 compare" in text
    assert analysis["population_fingerprint"] in text


def test_the_dossier_leaves_a_stale_result_out_unless_it_is_named(
    client, headers, project, analysed
):
    """A superseded population must not silently enter the dossier."""
    table, population = analysed["table"], analysed["population"]
    analysis = client.post(
        _url(
            project.id, f"/tables/{table['id']}/populations/{population['id']}/analyses"
        ),
        json={"method": "descriptive", "variables": ["age"]},
        headers=headers,
    ).json()
    # A newer population supersedes the one this analysis ran on.
    client.post(
        _url(project.id, f"/tables/{table['id']}/populations"),
        json={"name": "Narrower cohort", "criteria": ["anomalies::lvef_range"]},
        headers=headers,
    )

    default = client.get(
        _url(project.id, f"/tables/{table['id']}/dossier"), headers=headers
    )
    assert default.status_code == 200
    assert "5.1 descriptive" not in _dossier_text(default.content)

    named = client.get(
        _url(project.id, f"/tables/{table['id']}/dossier"),
        params={"analysis_id": analysis["id"]},
        headers=headers,
    )
    assert named.status_code == 200
    text = _dossier_text(named.content)
    assert "5.1 descriptive" in text
    assert "Stale result" in text


def test_the_dossier_refuses_an_unknown_analysis(client, headers, project, analysed):
    table = analysed["table"]
    response = client.get(
        _url(project.id, f"/tables/{table['id']}/dossier"),
        params={"analysis_id": "nope"},
        headers=headers,
    )
    assert response.status_code == 404


def test_a_viewer_may_download_the_dossier(
    client, headers, project, analysed, tmp_db, viewer
):
    from gazzali.crud.projects import add_member

    add_member(tmp_db, project.id, viewer.id, "viewer")
    token = client.post(
        "/api/v1/auth/login", json={"username": "reader", "password": "readpass1"}
    ).json()["token"]
    response = client.get(
        _url(project.id, f"/tables/{analysed['table']['id']}/dossier"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.content[:2] == b"PK"
