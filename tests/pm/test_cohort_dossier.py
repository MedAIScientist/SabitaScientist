"""The study dossier: what the Word document says, and what it refuses to claim.

The document is the one artefact a co-author reads, so these tests check its content
rather than its existence: the disclaimer, the provenance numbers, the exclusions with
their reasons, the missing-data paragraph, and the rule that a stale result is marked.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest
from docx import Document

from gazzali.cohort import dossier, engine, ingest, quality


@pytest.fixture(scope="module")
def prepared():
    """A small cohort, its population record and the analyses a dossier can hold."""
    rng = np.random.default_rng(13)
    n = 160
    frame = pd.DataFrame(
        {
            "age": rng.normal(62, 9, n).round(),
            "lvef": rng.normal(48, 12, n).round(1),
            "arm": rng.choice(["control", "treatment"], n),
        }
    )
    frame.loc[rng.random(n) < 0.2, "lvef"] = np.nan
    frame.loc[0, "age"] = 250  # fails the plausibility criterion
    table, _ = ingest.read_upload("cohort.csv", frame.to_csv(index=False).encode())

    config = {
        "mask_families": {
            "inclusion": {
                "operator": "all",
                "adult": {
                    "numeric": True,
                    "column": "age",
                    "lower_bound": 18,
                    "upper_bound": 110,
                },
            }
        }
    }
    result = engine.evaluate(table, config, ["inclusion::adult"])
    population = {
        **engine.population_record(result),
        "name": "Adults",
        "created_at": "2026-10-19T09:00:00Z",
        "superseded_by": None,
        "criteria": [
            {
                "id": "inclusion::adult",
                "family": "inclusion",
                "kind": "inclusion",
                "name": "adult",
            }
        ],
        "counts": [
            {"name": "adult", "kind": "inclusion", "marginal_base": n, "sequential": 1}
        ],
    }
    return {
        "table": table,
        "config": config,
        "result": result,
        "population": population,
        "compare": engine.run(table, "compare", {"outcome": "lvef", "group": "arm"}),
        "mcar": engine.run(table, "mcar", {"variables": ["age", "lvef"]}),
    }


def _analysis(
    outcome,
    identifier: str,
    *,
    stale: str | None = None,
    created: str = "2026-10-19T10:00:00Z",
):
    payload = {
        "id": identifier,
        "method": outcome.method,
        "n": outcome.n,
        "table": outcome.table,
        "result": outcome.result,
        "engine_version": "cohort-engine/1",
        "population_fingerprint": "f" * 16,
        "created_at": created,
    }
    if stale:
        payload["stale_reason"] = stale
    return payload


def _build(
    prepared,
    *,
    analyses,
    steps=None,
    quality_report=None,
    origin="public",
    dataset_id=None,
):
    return dossier.build_dossier(
        table={
            "name": "tutorial",
            "data_origin": origin,
            "dataset_id": dataset_id,
            "created_at": "2026-10-19T08:00:00Z",
        },
        project={"id": "p1", "name": "Heart failure cohort"},
        versions=[
            {
                "version_no": 1,
                "rows": 160,
                "columns": 3,
                "content_sha256": "0123456789abcdef" + "0" * 48,
                "created_at": "2026-10-19T08:00:00Z",
                "note": None,
            }
        ],
        population=prepared["population"],
        flow=engine.build_flow(prepared["result"], dataset="tutorial", n_loaded=160),
        quality=quality_report,
        steps=steps or [],
        analyses=analyses,
        generated_at="2026-10-19T12:00:00Z",
    )


def _document(payload: bytes) -> tuple[Document, str]:
    """The document, and all of its text — a hash or an exclusion reason lives in a table cell."""
    read = Document(io.BytesIO(payload))
    parts = [paragraph.text for paragraph in read.paragraphs]
    for table in read.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return read, "\n".join(parts)


def test_the_dossier_is_a_real_word_document(prepared):
    payload = _build(prepared, analyses=[_analysis(prepared["compare"], "a1")])
    assert payload[:2] == b"PK", "a .docx is a zip archive"
    read, _ = _document(payload)
    assert read.paragraphs, "the document has content"


def test_the_sections_appear_in_order(prepared):
    payload = _build(prepared, analyses=[_analysis(prepared["compare"], "a1")])
    read, _ = _document(payload)
    headings = [p.text for p in read.paragraphs if p.style.name.startswith("Heading")]
    ordered = [
        "1. Study and data provenance",
        "2. Participant flow (STROBE item 13)",
        "3. Data handling",
        "4. Missing data",
        "5. Results",
    ]
    for expected in ordered:
        assert expected in headings, expected
    # A STROBE flow without a diagram would be worse than a table: assert the table exists.
    assert any(table.rows[0].cells[0].text == "Step" for table in read.tables)


def test_it_states_that_it_is_not_a_compliance_certificate(prepared):
    """The one claim the document must never make."""
    payload = _build(prepared, analyses=[_analysis(prepared["compare"], "a1")])
    _, text = _document(payload)
    assert "not a compliance certificate" in text
    assert "does not certify" in text
    assert "STROBE" in text  # it names the guideline it could be mistaken for


def test_provenance_carries_the_hash_and_the_population_fingerprint(prepared):
    payload = _build(prepared, analyses=[_analysis(prepared["compare"], "a1")])
    _read, text = _document(payload)
    assert "0123456789abcdef" in text  # the version's content hash
    assert prepared["result"].fingerprint in text
    assert "160" in text


def test_a_public_cohort_says_no_ethics_approval_is_required(prepared):
    payload = _build(
        prepared, analyses=[_analysis(prepared["compare"], "a1")], origin="public"
    )
    _, text = _document(payload)
    assert "no ethics approval is linked" in text


def test_a_governed_cohort_names_its_dataset(prepared):
    payload = _build(
        prepared,
        analyses=[_analysis(prepared["compare"], "a1")],
        origin="governed",
        dataset_id="ds-42",
    )
    _, text = _document(payload)
    assert "governed dataset ds-42" in text
    assert "no ethics approval is linked" not in text


def test_the_flow_lists_the_exclusions_with_their_reasons(prepared):
    payload = _build(prepared, analyses=[_analysis(prepared["compare"], "a1")])
    read, text = _document(payload)
    assert "Not meeting: inclusion" in text
    assert "adult" in text  # the criterion behind the exclusion
    # 160 rows in, one excluded by the age criterion.
    rows = [
        [cell.text for cell in row.cells] for table in read.tables for row in table.rows
    ]
    assert any(
        row[0].startswith("Analysis population") and "159" in row[1] for row in rows
    )


def test_a_flow_that_does_not_add_up_is_called_out(prepared):
    flow = engine.build_flow(prepared["result"], dataset="tutorial", n_loaded=160)
    flow["inconsistencies"] = ["Analysis population: 158 rows, expected 159"]
    payload = dossier.build_dossier(
        table={
            "name": "t",
            "data_origin": "public",
            "dataset_id": None,
            "created_at": "t",
        },
        project={"id": "p", "name": "P"},
        versions=[],
        population=prepared["population"],
        flow=flow,
        quality=None,
        steps=[],
        analyses=[_analysis(prepared["compare"], "a1")],
        generated_at="t",
    )
    _, text = _document(payload)
    assert "The flow does not add up" in text


def test_data_handling_lists_a_derived_variable(prepared):
    steps = [
        {"seq": 0, "kind": "import", "params": {}, "data": {}},
        {
            "seq": 1,
            "kind": "derive",
            "params": {"name": "bmi"},
            "data": {"rows_in": 160, "rows_out": 160},
        },
    ]
    payload = _build(
        prepared, analyses=[_analysis(prepared["compare"], "a1")], steps=steps
    )
    _, text = _document(payload)
    assert "bmi" in text
    assert "hash-chained" in text


def test_data_handling_says_so_when_nothing_was_done(prepared):
    payload = _build(prepared, analyses=[_analysis(prepared["compare"], "a1")])
    _, text = _document(payload)
    assert "analysed as imported" in text


def test_data_quality_is_reported_when_available(prepared):
    report = quality.audit(prepared["table"], prepared["config"]).to_dict()
    payload = _build(
        prepared, analyses=[_analysis(prepared["compare"], "a1")], quality_report=report
    )
    _, text = _document(payload)
    assert "Data quality of the analysed version" in text
    assert "Completeness" in text


def test_missing_data_without_an_assessment_says_so(prepared):
    payload = _build(prepared, analyses=[_analysis(prepared["compare"], "a1")])
    _, text = _document(payload)
    assert "No missing-data assessment was included" in text


def test_mcar_is_reported_with_its_limit(prepared):
    payload = _build(
        prepared,
        analyses=[
            _analysis(prepared["compare"], "a1"),
            _analysis(prepared["mcar"], "a2"),
        ],
    )
    _, text = _document(payload)
    assert "Little's MCAR test" in text
    assert "chi-square =" in text
    assert "does not prove it" in text


def test_multiple_imputation_records_how_it_was_done(prepared):
    pooled = engine.run(
        prepared["table"],
        "multiple_imputation",
        {
            "target": "compare",
            "outcome": "lvef",
            "group": "arm",
            "m": 3,
            "maxit": 3,
            "seed": 7,
        },
    )
    payload = _build(prepared, analyses=[_analysis(pooled, "a3")])
    _, text = _document(payload)
    assert "3 imputations" in text
    assert "Rubin's rules" in text
    assert "Seed: 7" in text
    assert "Nothing singly imputed" in text


def test_a_missingness_test_is_not_repeated_as_a_result(prepared):
    payload = _build(
        prepared,
        analyses=[
            _analysis(prepared["compare"], "a1"),
            _analysis(prepared["mcar"], "a2"),
        ],
    )
    read, _ = _document(payload)
    headings = [p.text for p in read.paragraphs if p.style.name.startswith("Heading")]
    assert "5.1 compare" in headings
    assert not any("mcar" in heading for heading in headings)


def test_a_stale_result_is_marked_and_not_presented_as_current(prepared):
    payload = _build(
        prepared,
        analyses=[
            _analysis(prepared["compare"], "a1", stale="the population was superseded")
        ],
    )
    _, text = _document(payload)
    assert "Stale result" in text
    assert "must not be reported as current" in text


def test_methods_references_are_listed_once(prepared):
    payload = _build(
        prepared,
        analyses=[
            _analysis(prepared["compare"], "a1"),
            _analysis(prepared["mcar"], "a2"),
        ],
    )
    _, text = _document(payload)
    assert "Methods references" in text
    assert text.count("Mantel N (1966)") <= 1 or "Mantel" not in text


def test_the_document_says_when_and_by_what_it_was_generated(prepared):
    payload = _build(prepared, analyses=[_analysis(prepared["compare"], "a1")])
    _, text = _document(payload)
    assert "Generated 2026-10-19T12:00:00Z" in text
    assert "Gazzali cohort module" in text
