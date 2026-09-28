"""Tests for durable draft storage, restore, and AI-use disclosure.

The property under test is that a generated draft survives and can be read
back, and that the disclosure statement reports only what actually happened.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.publications import create_version, get_version
from EvoScientist.pm.crud.users import create_user

LONG_DRAFT = "Results: accuracy was 0.912 on the held-out split. " * 200


@pytest.fixture
def app(tmp_db: Path):
    import EvoScientist.pm.api.deps as deps_mod
    import EvoScientist.pm.api.routes.auth as auth_r
    import EvoScientist.pm.api.routes.projects as proj_r
    import EvoScientist.pm.api.routes.publications as pubs_r
    import EvoScientist.pm.crud.projects as proj_mod
    import EvoScientist.pm.crud.publications as pubs_mod
    import EvoScientist.pm.crud.users as users_mod

    for mod in [deps_mod, users_mod, proj_mod, pubs_mod, auth_r, proj_r, pubs_r]:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda _db=tmp_db: _db
    return create_app(tmp_db)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def user_id(tmp_db):
    return create_user(tmp_db, username="pi", password_hash=hash_password("pass")).id


@pytest.fixture
def headers(tmp_db, client, user_id):
    resp = client.post("/api/v1/auth/login", json={"username": "pi", "password": "pass"})
    return {"Authorization": f"Bearer {resp.json()['token']}"}


@pytest.fixture
def publication(client, headers):
    proj = client.post("/api/v1/projects", json={"name": "Study"}, headers=headers).json()
    pub = client.post(
        "/api/v1/publications",
        json={"title": "A Paper", "project_id": proj["id"]},
        headers=headers,
    ).json()
    return pub["id"]


# ── Durable drafts ────────────────────────────────────────────────────────────


def test_long_draft_survives_intact(tmp_db, publication, user_id):
    """A draft longer than any old truncation limit must round-trip byte-exact."""
    version = create_version(
        tmp_db, publication, created_by=user_id,
        content=LONG_DRAFT, section="results", generated_by="ai-agent",
    )
    assert len(LONG_DRAFT) > 800
    assert get_version(tmp_db, version.id).content == LONG_DRAFT


def test_version_listing_omits_content_but_reports_length(client, headers, tmp_db, publication, user_id):
    create_version(tmp_db, publication, created_by=user_id, content=LONG_DRAFT, section="results")
    listed = client.get(f"/api/v1/publications/{publication}/versions", headers=headers).json()
    assert listed[0]["content"] is None
    assert listed[0]["content_length"] == len(LONG_DRAFT)
    assert listed[0]["section"] == "results"


def test_single_version_endpoint_returns_full_text(client, headers, tmp_db, publication, user_id):
    version = create_version(tmp_db, publication, created_by=user_id, content=LONG_DRAFT)
    resp = client.get(
        f"/api/v1/publications/{publication}/versions/{version.id}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == LONG_DRAFT


def test_version_from_another_publication_is_not_readable(client, headers, tmp_db, publication, user_id):
    other = client.post(
        "/api/v1/publications", json={"title": "Other"}, headers=headers
    ).json()["id"]
    version = create_version(tmp_db, other, created_by=user_id, content="secret")
    resp = client.get(
        f"/api/v1/publications/{publication}/versions/{version.id}", headers=headers
    )
    assert resp.status_code == 404


def test_created_version_via_api_stores_content(client, headers, publication):
    resp = client.post(
        f"/api/v1/publications/{publication}/versions",
        json={"notes": "manual", "content": "Hand-written methods.", "section": "methods"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["content"] == "Hand-written methods."
    assert resp.json()["generated_by"] == "human"


# ── Restore ───────────────────────────────────────────────────────────────────


def test_restore_carries_the_text_forward(client, headers, tmp_db, publication, user_id):
    """A restore that copies only the note restores nothing."""
    original = create_version(
        tmp_db, publication, created_by=user_id, content=LONG_DRAFT, section="results",
    )
    create_version(tmp_db, publication, created_by=user_id, content="a worse draft")

    resp = client.post(
        f"/api/v1/publications/{publication}/versions/{original.id}/restore", headers=headers
    )
    assert resp.status_code == 200

    restored = get_version(tmp_db, resp.json()["new_version_id"])
    assert restored.content == LONG_DRAFT
    assert restored.section == "results"


# ── AI disclosure ─────────────────────────────────────────────────────────────


def test_disclosure_says_none_when_no_ai_was_used(client, headers, tmp_db, publication, user_id):
    create_version(tmp_db, publication, created_by=user_id, content="Typed by hand",
                   generated_by="human")
    body = client.get(f"/api/v1/publications/{publication}/ai-disclosure", headers=headers).json()
    assert body["ai_version_count"] == 0
    assert "No AI-assisted drafting was recorded" in body["statement"]


def test_disclosure_reports_recorded_models_and_sections(client, headers, tmp_db, publication, user_id):
    create_version(tmp_db, publication, created_by=user_id, content="x",
                   section="results", generated_by="ai-direct", model="claude-opus-5")
    create_version(tmp_db, publication, created_by=user_id, content="y",
                   section="methods", generated_by="ai-agent", model="claude-opus-5")
    create_version(tmp_db, publication, created_by=user_id, content="z", generated_by="human")

    body = client.get(f"/api/v1/publications/{publication}/ai-disclosure", headers=headers).json()
    assert body["ai_version_count"] == 2
    assert body["human_version_count"] == 1
    assert body["models_used"] == ["claude-opus-5"]
    assert body["sections"] == ["methods", "results"]
    assert "claude-opus-5" in body["statement"]


def test_disclosure_does_not_invent_a_model_name(client, headers, tmp_db, publication, user_id):
    """Runner-generated text has no recorded model; the statement must not guess."""
    create_version(tmp_db, publication, created_by=user_id, content="x",
                   section="results", generated_by="ai-agent", model=None)
    body = client.get(f"/api/v1/publications/{publication}/ai-disclosure", headers=headers).json()
    assert body["models_used"] == []
    assert "unrecorded language model" in body["statement"]


def test_prompt_fingerprint_is_stable_and_not_the_prompt():
    from EvoScientist.pm.api.routes.drafting_helpers import prompt_fingerprint

    prompt = "Write a Results section. Patient 4 had a p-value of 0.03."
    digest = prompt_fingerprint(prompt)
    assert digest == prompt_fingerprint(prompt)
    assert digest != prompt_fingerprint(prompt + " ")
    assert "p-value" not in digest
    assert len(digest) == 16
