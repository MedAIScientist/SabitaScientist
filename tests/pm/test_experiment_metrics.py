"""Tests for structured experiment metrics and prompt grounding.

The property under test is not "metrics can be stored" but "numbers that were
never recorded cannot reach a drafting prompt".
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.experiment_metrics import create_metrics, list_metrics
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.metrics_csv import parse_metrics_csv


@pytest.fixture
def app(tmp_db: Path):
    """App with every DB lookup pinned to tmp_db.

    Other test modules overwrite ``get_db_path`` on these shared modules
    permanently, so each binding is rebound here with a default argument
    rather than a closure — otherwise this test depends on file ordering.
    """
    import EvoScientist.pm.api.deps as deps_mod
    import EvoScientist.pm.api.routes.attachments as att_r
    import EvoScientist.pm.api.routes.auth as auth_r
    import EvoScientist.pm.api.routes.drafting_helpers as helpers_mod
    import EvoScientist.pm.api.routes.experiments as exps_r
    import EvoScientist.pm.api.routes.projects as proj_r
    import EvoScientist.pm.crud.experiment_entries as entries_mod
    import EvoScientist.pm.crud.experiments as exps_mod
    import EvoScientist.pm.crud.projects as proj_mod
    import EvoScientist.pm.crud.users as users_mod
    from EvoScientist.pm.db import get_db as _real_get_db

    for mod in [deps_mod, users_mod, proj_mod, exps_mod, entries_mod,
                auth_r, proj_r, exps_r, att_r, helpers_mod]:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda _db=tmp_db: _db
    att_r.get_db = lambda _db=tmp_db: _real_get_db(_db)
    return create_app(tmp_db)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def headers(tmp_db, client):
    create_user(tmp_db, username="pi", password_hash=hash_password("pass"))
    resp = client.post("/api/v1/auth/login", json={"username": "pi", "password": "pass"})
    return {"Authorization": f"Bearer {resp.json()['token']}"}


@pytest.fixture
def experiment(client, headers):
    proj = client.post("/api/v1/projects", json={"name": "Trial"}, headers=headers).json()
    exp = client.post(
        f"/api/v1/projects/{proj['id']}/experiments",
        json={"name": "Ablation"}, headers=headers,
    ).json()
    return proj["id"], exp["id"]


# ── CSV parsing ───────────────────────────────────────────────────────────────


def test_parses_wide_csv_one_metric_per_numeric_column():
    metrics = parse_metrics_csv("split,accuracy,f1,n\ntest,0.912,0.887,1200\n")
    by_name = {m.name: m for m in metrics}
    assert by_name["accuracy"].value == pytest.approx(0.912)
    assert by_name["f1"].value == pytest.approx(0.887)
    assert by_name["accuracy"].split == "test"
    assert by_name["accuracy"].n == 1200


def test_parses_long_csv_with_metric_value_columns():
    metrics = parse_metrics_csv(
        "metric,value,unit,stderr\nlatency,42.5,ms,1.3\nthroughput,880,req/s,\n"
    )
    assert len(metrics) == 2
    assert metrics[0].name == "latency"
    assert metrics[0].unit == "ms"
    assert metrics[0].stderr == pytest.approx(1.3)
    assert metrics[1].stderr is None


def test_parses_tab_separated():
    metrics = parse_metrics_csv("model\tauc\nbaseline\t0.71\n")
    assert [(m.name, m.value) for m in metrics] == [("auc", 0.71)]


def test_ambiguous_numbers_are_dropped_not_guessed():
    """'1,234' and '85%' are ambiguous; a missing metric beats a wrong one."""
    metrics = parse_metrics_csv("metric,value\ncount,\"1,234\"\nrate,85%\ngood,0.5\n")
    assert [m.name for m in metrics] == ["good"]


def test_garbage_input_yields_no_metrics():
    assert parse_metrics_csv("") == []
    assert parse_metrics_csv("this is not a table at all") == []


def test_multiple_rows_get_distinct_split_labels():
    metrics = parse_metrics_csv("accuracy\n0.8\n0.9\n")
    assert {m.split for m in metrics} == {"row 1", "row 2"}


# ── Storage + API ─────────────────────────────────────────────────────────────


def test_metric_roundtrip_through_api(client, headers, experiment):
    project_id, exp_id = experiment
    created = client.post(
        f"/api/v1/projects/{project_id}/experiments/{exp_id}/metrics",
        json={"name": "auc", "value": 0.93, "split": "holdout", "n": 300},
        headers=headers,
    )
    assert created.status_code == 201

    listed = client.get(
        f"/api/v1/projects/{project_id}/experiments/{exp_id}/metrics", headers=headers
    ).json()
    assert [(m["name"], m["value"], m["split"]) for m in listed] == [("auc", 0.93, "holdout")]

    assert client.delete(
        f"/api/v1/projects/{project_id}/experiments/{exp_id}/metrics/{created.json()['id']}",
        headers=headers,
    ).status_code == 204
    assert client.get(
        f"/api/v1/projects/{project_id}/experiments/{exp_id}/metrics", headers=headers
    ).json() == []


def test_csv_upload_records_metrics(client, headers, experiment, tmp_db):
    """A results CSV attached to an entry becomes queryable structured metrics."""
    from unittest.mock import patch

    project_id, exp_id = experiment
    entry = client.post(
        f"/api/v1/projects/{project_id}/experiments/{exp_id}/entries",
        json={"type": "result", "title": "Final run"}, headers=headers,
    ).json()

    with patch("EvoScientist.pm.api.routes.attachments.upload_file"), \
         patch("EvoScientist.pm.api.routes.attachments.generate_presigned_url", return_value="http://x"), \
         patch("EvoScientist.pm.api.routes.attachments.get_db_path", lambda: tmp_db):
        resp = client.post(
            f"/api/v1/projects/{project_id}/experiments/{exp_id}/entries/{entry['id']}/attachments",
            files={"file": ("results.csv", b"split,accuracy\ntest,0.88\n", "text/csv")},
            headers=headers,
        )

    assert resp.status_code == 201
    assert resp.json()["metrics_parsed"] == 1
    assert [m.name for m in list_metrics(tmp_db, exp_id)] == ["accuracy"]


# ── Grounding ─────────────────────────────────────────────────────────────────


def test_context_states_none_when_no_metrics_recorded(app, tmp_db, experiment):
    """No metrics must read as an explicit refusal, not an empty gap."""
    from EvoScientist.pm.api.routes.drafting_helpers import render_metrics_block

    _, exp_id = experiment
    block = render_metrics_block(exp_id)
    assert "NONE" in block
    assert "Report no numbers" in block


def test_context_contains_recorded_values(app, tmp_db, experiment):
    from EvoScientist.pm.api.routes.drafting_helpers import render_metrics_block
    from EvoScientist.pm.metrics_csv import ParsedMetric

    _, exp_id = experiment
    create_metrics(
        tmp_db, exp_id, [ParsedMetric(name="auc", value=0.93, split="holdout", n=300)]
    )
    block = render_metrics_block(exp_id)
    assert "auc" in block
    assert "0.93" in block
    assert "holdout" in block


def test_result_entries_are_never_truncated():
    """Notes may be clipped; a result entry is the record and must survive whole."""
    from EvoScientist.pm.api.routes.drafting_helpers import _entry_body

    class _Entry:
        def __init__(self, type_, body):
            self.type = type_
            self.body = body

    long_body = "x" * 3000
    assert _entry_body(_Entry("result", long_body)) == long_body
    assert len(_entry_body(_Entry("note", long_body))) < 600


def test_grounding_rule_is_attached_to_section_prompts():
    from EvoScientist.pm.api.routes.drafting import _build_section_prompt

    prompt = _build_section_prompt("some context", "results", "standard")
    assert "Recorded metrics" in prompt
    assert "[TBD: not recorded]" in prompt
