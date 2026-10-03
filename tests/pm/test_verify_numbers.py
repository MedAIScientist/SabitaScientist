"""Verified result reporting: AI drafts may only state recorded numbers (paper §3.4)."""

from __future__ import annotations

from pathlib import Path

from gazzali.auth import hash_password
from gazzali.crud.experiment_metrics import create_metrics
from gazzali.crud.experiments import create_experiment
from gazzali.crud.projects import create_project
from gazzali.crud.publications import (
    create_publication,
    create_version,
    link_experiment,
)
from gazzali.crud.users import create_user
from gazzali.metrics_csv import ParsedMetric
from gazzali.verify_numbers import MARK, verify

RECORDED = [0.912, 0.034, 120.0]


def test_matches_within_one_percent_and_percent_forms() -> None:
    _, s = verify("Recall was 0.912 ± 0.034, i.e. 91.2%, n = 120.", RECORDED, "results")
    assert (s["checked"], s["verified"], s["unverified"]) == (4, 4, 0)


def test_unrecorded_number_in_results_is_marked() -> None:
    text, s = verify("Accuracy reached 0.97 on the test set.", RECORDED, "results")
    assert text == f"Accuracy reached 0.97{MARK} on the test set."
    assert s["unverified_in_results"] == 1
    assert s["examples"][0]["value"] == "0.97"


def test_years_counts_and_references_are_not_claims() -> None:
    _, s = verify("In 2024 we ran 5 seeds (see Table 3, Section 4.1) [12].", RECORDED, "results")
    assert s["checked"] == 0


def test_introduction_numbers_are_counted_not_marked() -> None:
    text, s = verify("Diabetes affects 537 million adults.", RECORDED, "introduction")
    assert MARK not in text
    assert (s["unverified"], s["unverified_in_results"]) == (1, 0)


def test_full_draft_marks_only_results_sections() -> None:
    draft = "# Introduction\nIt affects 537 million adults.\n\n## Results\nRecall 0.80 vs 0.912.\n"
    text, _ = verify(draft, RECORDED, None)
    assert "537 million" in text
    assert "537 million" + MARK not in text
    assert f"0.80{MARK}" in text
    assert f"0.912{MARK}" not in text


def test_ai_versions_are_checked_against_linked_experiments(tmp_db: Path) -> None:
    u = create_user(tmp_db, "ayse", hash_password("pw123456"))
    p = create_project(tmp_db, "DR", u.id)
    exp = create_experiment(tmp_db, p.id, "weights", u.id)
    create_metrics(tmp_db, exp.id, [ParsedMetric(name="recall", value=0.912)])
    pub = create_publication(tmp_db, "Paper", u.id, project_id=p.id)
    link_experiment(tmp_db, pub.id, exp.id)
    v = create_version(tmp_db, pub.id, u.id, content="Recall 0.912 and AUC 0.99.", section="results", generated_by="ai-agent")
    assert v.content == f"Recall 0.912 and AUC 0.99{MARK}."
    assert (v.verification["verified"], v.verification["unverified"]) == (1, 1)
    human = create_version(tmp_db, pub.id, u.id, content="AUC 0.99.", section="results", generated_by="human")
    assert human.content == "AUC 0.99."
    assert human.verification is None
