"""Tests for AI usage accounting.

The property under test is not "a row is inserted" but "the numbers a supervisor
sees can be trusted": provider-reported totals are never mixed with estimates,
access does not widen silently, and a failure to record usage never fails the work
that produced it.
"""

from __future__ import annotations

import pytest

from gazzali.auth import hash_password
from gazzali.crud.ai_usage import (
    UsageContext,
    extract_usage,
    list_usage,
    record_usage,
    record_usage_safely,
    summarize_usage,
)
from gazzali.crud.projects import create_project
from gazzali.crud.publications import create_publication
from gazzali.crud.users import create_user


@pytest.fixture
def users(tmp_db):
    prof = create_user(tmp_db, "prof", hash_password("pw"), role="professor")
    stud = create_user(tmp_db, "stud", hash_password("pw"), role="student")
    other = create_user(tmp_db, "other", hash_password("pw"), role="student")
    return prof, stud, other


@pytest.fixture
def paper(tmp_db, users):
    """A real project and publication: usage rows carry real foreign keys."""
    _prof, stud, _other = users
    project = create_project(tmp_db, name="Imaging study", created_by=stud.id)
    publication = create_publication(
        tmp_db, title="A paper", created_by=stud.id, project_id=project.id
    )
    return project, publication


# ── Recording ────────────────────────────────────────────────────────────────


def test_provider_reported_counts_are_kept_as_measurements(tmp_db, users) -> None:
    _prof, stud, _other = users
    record_usage(
        tmp_db,
        context=UsageContext(task="draft-section", user_id=stud.id),
        model="llama-3.3-70b",
        prompt_tokens=1200,
        completion_tokens=800,
        total_tokens=2000,
    )
    summary = summarize_usage(tmp_db, user_id=stud.id, days=None)
    assert summary["tokens"]["provider_reported"] == 2000
    assert summary["tokens"]["estimated"] == 0


def test_missing_usage_falls_back_to_a_labelled_estimate(tmp_db, users) -> None:
    """A provider that says nothing must not be reported as if it had."""
    _prof, stud, _other = users
    record_usage(
        tmp_db,
        context=UsageContext(task="revise", user_id=stud.id),
        model="some-model",
        prompt_chars=400,
        output_chars=80,
    )
    rows = list_usage(tmp_db, user_id=stud.id)
    assert rows[0].token_source == "estimated"
    assert rows[0].prompt_tokens == 100
    assert rows[0].completion_tokens == 20

    summary = summarize_usage(tmp_db, user_id=stud.id, days=None)
    assert summary["tokens"]["estimated"] == 120
    assert summary["tokens"]["provider_reported"] == 0


def test_estimates_and_measurements_are_never_summed_together(tmp_db, users) -> None:
    _prof, stud, _other = users
    record_usage(
        tmp_db,
        context=UsageContext(task="draft-section", user_id=stud.id),
        model="m",
        total_tokens=1000,
    )
    record_usage(
        tmp_db,
        context=UsageContext(task="revise", user_id=stud.id),
        model="m",
        prompt_chars=400,
    )

    summary = summarize_usage(tmp_db, user_id=stud.id, days=None)
    assert summary["tokens"]["provider_reported"] == 1000
    assert summary["tokens"]["estimated"] == 100
    assert summary["calls"] == 2
    # Two tasks, because the breakdown is what makes the total actionable.
    assert {row["task"] for row in summary["by_task"]} == {"draft-section", "revise"}
    assert {row["model"] for row in summary["by_model"]} == {"m"}


def test_usage_is_attributed_to_the_paper_and_the_project(tmp_db, users, paper) -> None:
    _prof, stud, _other = users
    project, publication = paper
    record_usage(
        tmp_db,
        context=UsageContext(
            task="respond-to-reviewers",
            user_id=stud.id,
            project_id=project.id,
            publication_id=publication.id,
            run_id=f"response-{publication.id}",
            source="agent",
        ),
        model="m",
        total_tokens=500,
    )
    by_paper = summarize_usage(tmp_db, publication_id=publication.id, days=None)
    assert by_paper["calls"] == 1
    by_project = summarize_usage(tmp_db, project_id=project.id, days=None)
    assert by_project["calls"] == 1
    by_unrelated_project = summarize_usage(tmp_db, project_id="no-such-project", days=None)
    assert by_unrelated_project["calls"] == 0


def test_recording_never_raises_when_the_database_is_unusable(tmp_path) -> None:
    """Bookkeeping must not be able to fail a run that already produced a draft."""
    # A directory can never be opened as a SQLite database.
    result = record_usage_safely(
        tmp_path, context=UsageContext(task="draft-section"), model="m", total_tokens=1
    )
    assert result is None


def test_extract_usage_reads_both_provider_shapes() -> None:
    class _Message:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    assert extract_usage(_Message(usage_metadata={
        "input_tokens": 10, "output_tokens": 5, "total_tokens": 15
    })) == (10, 5, 15)

    assert extract_usage(_Message(response_metadata={
        "token_usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}
    })) == (7, 3, 10)

    assert extract_usage(_Message()) == (None, None, None)


# ── Access control ───────────────────────────────────────────────────────────


def _token(client, username: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "pw"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_student_sees_only_their_own_usage(client, tmp_db, users) -> None:
    _prof, stud, other = users
    record_usage(
        tmp_db,
        context=UsageContext(task="draft-section", user_id=stud.id),
        model="m",
        total_tokens=100,
    )
    record_usage(
        tmp_db,
        context=UsageContext(task="draft-section", user_id=other.id),
        model="m",
        total_tokens=999,
    )

    token = _token(client, "stud")
    body = client.get("/api/v1/ai/usage/summary", headers=_h(token)).json()
    assert body["calls"] == 1
    assert body["tokens"]["provider_reported"] == 100


def test_student_cannot_read_the_platform_wide_total(client, users) -> None:
    token = _token(client, "stud")
    resp = client.get(
        "/api/v1/ai/usage/summary?scope=all", headers=_h(token)
    )
    assert resp.status_code == 403


def test_student_cannot_read_another_students_usage(client, users) -> None:
    _prof, _stud, other = users
    resp = client.get(
        f"/api/v1/ai/usage/summary?scope=user&user_id={other.id}",
        headers=_h(_token(client, "stud")),
    )
    assert resp.status_code == 403


def test_professor_reads_only_own_lab_students_and_admins_read_the_platform(client, tmp_db, users) -> None:
    """A professor sees the AI usage of the students in the labs they lead, nobody
    else's; platform-wide usage is for admins."""
    from gazzali.crud.labs import add_member, create_lab

    prof, stud, other = users
    for who in (stud, other):
        record_usage(tmp_db, context=UsageContext(task="revise", user_id=who.id), model="m", total_tokens=250)
    lab = create_lab(tmp_db, name="Imaging Lab", pi_id=prof.id)
    add_member(tmp_db, lab.id, prof.id, "pi")
    add_member(tmp_db, lab.id, stud.id, "phd")  # `other` is not in the lab

    token = _token(client, "prof")
    one = client.get(f"/api/v1/ai/usage/summary?scope=user&user_id={stud.id}", headers=_h(token))
    assert one.status_code == 200 and one.json()["tokens"]["provider_reported"] == 250
    assert client.get(f"/api/v1/ai/usage/summary?scope=user&user_id={other.id}", headers=_h(token)).status_code == 403
    assert client.get("/api/v1/ai/usage/summary?scope=all", headers=_h(token)).status_code == 403
    assert client.get("/api/v1/ai/usage/records?scope=all", headers=_h(token)).status_code == 403


def test_publication_scoped_usage_is_readable_from_the_paper(
    client, tmp_db, users, paper
) -> None:
    _prof, stud, _other = users
    _project, publication = paper
    record_usage(
        tmp_db,
        context=UsageContext(
            task="draft-section", user_id=stud.id, publication_id=publication.id
        ),
        model="m",
        total_tokens=310,
    )
    token = _token(client, "stud")
    body = client.get(
        f"/api/v1/ai/usage/summary?publication_id={publication.id}", headers=_h(token)
    ).json()
    assert body["tokens"]["provider_reported"] == 310
    assert body["by_task"][0]["label"] == "draft-section"


def test_usage_endpoints_require_authentication(client) -> None:
    assert client.get("/api/v1/ai/usage/summary").status_code == 401
    assert client.get("/api/v1/ai/usage/records").status_code == 401


def test_records_are_capped_and_newest_first(tmp_db, users) -> None:
    _prof, stud, _other = users
    for index in range(5):
        record_usage(
            tmp_db,
            context=UsageContext(task=f"task-{index}", user_id=stud.id),
            model="m",
            total_tokens=index,
        )
    rows = list_usage(tmp_db, user_id=stud.id, limit=3)
    assert len(rows) == 3
    assert rows[0].created_at >= rows[-1].created_at


def test_usage_rows_survive_a_window_filter(tmp_db, users) -> None:
    _prof, stud, _other = users
    record_usage(
        tmp_db,
        context=UsageContext(task="draft-section", user_id=stud.id),
        model="m",
        total_tokens=10,
    )
    assert summarize_usage(tmp_db, days=30)["calls"] == 1
    assert summarize_usage(tmp_db, days=1)["calls"] == 1
