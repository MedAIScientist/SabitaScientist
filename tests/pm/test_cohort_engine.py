"""The cohort engine, without a database: reading files, quality, transforms, statistics.

These tests exercise ``gazzali/cohort`` as a library. The API layer is covered in
``test_cohort_api.py``; keeping the split means a failure here is a statistics or
parsing problem, never a routing one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gazzali.cohort import analyses, engine, ingest, quality, transform


@pytest.fixture(scope="module")
def cohort_frame() -> pd.DataFrame:
    """A small synthetic cohort with the defects the scorecard is meant to notice."""
    rng = np.random.default_rng(11)
    n = 240
    frame = pd.DataFrame(
        {
            "age": rng.normal(61, 10, n).round(),
            "sex": rng.choice(["Female", "Male"], n, p=[0.55, 0.45]),
            "nyha": rng.choice(["II", "III", "IV"], n, p=[0.5, 0.35, 0.15]),
            "lvef": rng.normal(48, 12, n).round(1),
            "weight_kg": rng.normal(78, 14, n).round(1),
            "height_cm": rng.normal(168, 9, n).round(1),
        }
    )
    frame.loc[rng.choice(n, 18, replace=False), "lvef"] = np.nan
    # One row written 'male', one implausible age, one duplicated record.
    frame.loc[0, "sex"] = "male"
    frame.loc[1, "age"] = 250
    frame = pd.concat([frame, frame.iloc[[2]]], ignore_index=True)
    return frame.reset_index(drop=True)


@pytest.fixture(scope="module")
def two_group_frame(cohort_frame: pd.DataFrame) -> pd.DataFrame:
    """The cohort with the mis-coded 'male' rows removed: a clean two-group comparison."""
    return cohort_frame[cohort_frame["sex"].isin(["Female", "Male"])].copy()


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------


def test_read_upload_detects_semicolon_and_assigns_row_ids():
    payload = b"age;sex\n61;Female\n70;Male\n"
    frame, report = ingest.read_upload("cohort.csv", payload)
    assert report.delimiter == ";"
    assert report.rows == 2
    assert list(frame.columns) == ["age", "sex"]
    assert frame.index.name == "__row_id"
    assert frame.index.is_unique


def test_read_upload_detects_latin1_and_reports_encoding():
    payload = "age;centre\n61;Zürich\n".encode("cp1252")
    frame, report = ingest.read_upload("c.csv", payload)
    assert report.encoding == "cp1252"
    assert frame.loc[0, "centre"] == "Zürich"


def test_read_upload_counts_blank_lines_as_skipped():
    payload = b"age,sex\n61,F\n\n70,M\n"
    _frame, report = ingest.read_upload("c.csv", payload)
    assert report.rows == 2
    assert report.lines == 3  # the blank line is not counted as a record


@pytest.mark.parametrize("suffix", [".json", ".xls", ".pdf"])
def test_read_upload_rejects_unsupported_types(suffix):
    with pytest.raises(ingest.IngestError):
        ingest.read_upload(f"cohort{suffix}", b"whatever")


def test_read_upload_rejects_duplicate_columns():
    with pytest.raises(ingest.IngestError, match="duplicate column"):
        ingest.read_upload("c.csv", b"age,age\n1,2\n")


def test_columns_payload_classifies_kinds(cohort_frame):
    columns = {item["name"]: item for item in ingest.columns_payload(cohort_frame)}
    assert columns["age"]["kind"] == "numeric"
    assert columns["sex"]["kind"] == "categorical"
    assert columns["sex"]["levels"] == 3


# ---------------------------------------------------------------------------
# quality
# ---------------------------------------------------------------------------


def test_quality_scores_every_dimension(cohort_frame):
    report = quality.audit(cohort_frame)
    keys = [dimension["key"] for dimension in report.dimensions]
    assert keys == [
        "completeness",
        "uniqueness",
        "consistency",
        "uniformity",
        "validity",
    ]
    assert 0.0 <= report.score <= 1.0
    assert sum(dimension["weight"] for dimension in report.dimensions) == pytest.approx(
        1.0
    )


def test_quality_notices_a_duplicated_record(cohort_frame):
    """A duplicate inflates every N in the study, so it must be reported, not absorbed."""
    report = quality.audit(cohort_frame)
    assert report.duplicates["rows"] == 1
    uniformity = next(d for d in report.dimensions if d["key"] == "uniqueness")
    assert uniformity["score"] < 1.0
    assert any("duplicated row" in warning for warning in report.warnings)


def test_quality_reports_mixed_case_as_a_uniformity_issue(cohort_frame):
    report = quality.audit(cohort_frame)
    assert any(item["column"] == "sex" for item in report.non_uniform)
    uniformity = next(d for d in report.dimensions if d["key"] == "uniformity")
    assert uniformity["score"] < 1.0
    assert any("more than one way" in warning for warning in report.warnings)


def test_quality_reports_outliers_and_missing(cohort_frame):
    report = quality.audit(cohort_frame)
    assert any(item["column"] == "lvef" for item in report.missing)
    assert any(item["column"] == "age" for item in report.outliers)


def test_quality_evaluates_the_study_clinical_rules(cohort_frame):
    config = {
        "mask_families": {
            "inclusion": {
                "operator": "all",
                "plausible_age": {
                    "numeric": True,
                    "column": "age",
                    "lower_bound": 18,
                    "upper_bound": 110,
                },
            }
        }
    }
    report = quality.audit(cohort_frame, config)
    rule = next(
        item for item in report.clinical_rules if item["name"] == "plausible_age"
    )
    assert rule["rows"] >= 1


def test_quality_survives_a_broken_rule_without_failing(cohort_frame):
    report = quality.audit(
        cohort_frame,
        {
            "mask_families": {
                "x": {"operator": "all", "missing": {"bounds": {"nope": [0, 1]}}}
            }
        },
    )
    assert any("cannot be evaluated" in warning for warning in report.warnings)


# ---------------------------------------------------------------------------
# transforms
# ---------------------------------------------------------------------------


def test_derive_computes_a_column(cohort_frame):
    out = transform.derive(
        cohort_frame, "bmi", "df['weight_kg'] / (df['height_cm']/100)**2"
    )
    assert "bmi" in out.columns
    expected = cohort_frame["weight_kg"] / (cohort_frame["height_cm"] / 100) ** 2
    assert np.allclose(out["bmi"], expected)


def test_derive_rejects_unsafe_expressions(cohort_frame):
    with pytest.raises(transform.TransformError):
        transform.derive(cohort_frame, "x", "__import__('os').system('true')")


def test_derive_rejects_missing_columns(cohort_frame):
    with pytest.raises(transform.TransformError, match="not in this version"):
        transform.derive(cohort_frame, "x", "df['nope'] * 2")


def test_derive_rejects_an_existing_column_unless_overwrite(cohort_frame):
    with pytest.raises(transform.TransformError, match="already exists"):
        transform.derive(cohort_frame, "age", "df['age'] + 1")
    out = transform.derive(cohort_frame, "age", "df['age'] + 1", overwrite=True)
    assert np.allclose(out["age"], cohort_frame["age"] + 1)


def test_derive_rejects_a_wrong_length_result(cohort_frame):
    with pytest.raises(transform.TransformError):
        transform.derive(cohort_frame, "x", "df['age'].head(3)")


def test_filter_keep_and_drop(cohort_frame):
    kept, removed = transform.filter_rows(cohort_frame, action="keep", row_ids=[[0, 9]])
    assert len(kept) == 10
    assert removed == len(cohort_frame) - 10
    dropped, removed_drop = transform.filter_rows(
        cohort_frame, action="drop", row_ids=[[0, 9]]
    )
    assert len(dropped) == len(cohort_frame) - 10
    assert removed_drop == 10


def test_filter_rejects_unknown_ids(cohort_frame):
    with pytest.raises(transform.TransformError, match="not in this version"):
        transform.filter_rows(cohort_frame, action="drop", row_ids=[[10**6, 10**6 + 5]])


# ---------------------------------------------------------------------------
# population
# ---------------------------------------------------------------------------


def test_evaluate_population_keeps_rows_and_reports_stages(cohort_frame):
    config = {
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
            "anomalies": {
                "operator": "any",
                "lvef_range": {"bounds": {"lvef": [5, 90]}},
            },
        }
    }
    result = engine.evaluate(cohort_frame, config, ["inclusion::plausible_age"])
    assert result.ok
    assert result.n_base == len(cohort_frame)
    assert result.n_included == len(cohort_frame) - 1  # the implausible age
    assert len(result.stages) == 1
    assert result.fingerprint


def test_evaluate_rejects_unknown_criteria(cohort_frame):
    with pytest.raises(engine.EngineError, match="unknown criteria"):
        engine.evaluate(cohort_frame, {}, ["inclusion::nope"])


def test_population_frame_refuses_an_empty_population(cohort_frame):
    config = {
        "mask_families": {
            "inclusion": {
                "operator": "all",
                "nobody": {"expression": "df['age'] > 10000"},
            }
        }
    }
    result = engine.evaluate(cohort_frame, config, ["inclusion::nobody"])
    with pytest.raises(engine.EngineError, match="empty"):
        engine.population_frame(cohort_frame, result)


def test_catalogue_payload_lists_families(cohort_frame):
    config = {
        "mask_families": {
            "inclusion": {
                "operator": "all",
                "adult": {"expression": "df['age'] >= 18"},
            },
            "anomalies": {
                "operator": "any",
                "lvef_range": {"bounds": {"lvef": [5, 90]}},
            },
        }
    }
    payload = engine.catalogue_payload(config)
    assert [item["kind"] for item in payload] == ["inclusion", "exclusion"]
    assert payload[0]["columns"] == ["age"]
    assert payload[1]["columns"] == ["lvef"]


# ---------------------------------------------------------------------------
# analyses
# ---------------------------------------------------------------------------


def test_descriptive_reports_both_summaries_and_missing(cohort_frame):
    outcome = analyses.descriptive(cohort_frame, ["age", "sex"])
    numeric = outcome.table["rows"][0]
    assert numeric["kind"] == "numeric"
    assert numeric["detail"]["stats"]["missing"] == 0
    assert numeric["detail"]["stats"]["median"] is not None
    categorical = outcome.table["rows"][1]
    assert "levels" in categorical["detail"]["stats"]


def test_table_one_has_a_column_per_group_and_a_p_value(cohort_frame):
    outcome = analyses.table_one(cohort_frame, ["age", "lvef"], group="nyha")
    table = outcome.table
    assert table["columns"][0]["key"] == "overall"
    assert table["columns"][-1]["key"] == "p"
    age_row = table["rows"][0]
    assert age_row["cells"]["overall"]
    assert age_row["p"] is not None
    assert age_row["p_adjusted"] is not None
    assert age_row["p_adjusted"] >= age_row["p"] - 1e-12


def test_table_one_uses_one_summary_style_per_variable(cohort_frame):
    """A mean in one column and a median in the next, in one row, would be a defect."""
    outcome = analyses.table_one(cohort_frame, ["lvef"], group="nyha")
    row = outcome.table["rows"][0]
    values = [row["cells"][f"g:{level}"] for level in ("II", "III", "IV")]
    kinds = {"parenthesis" if "(" in value else "bracket" for value in values}
    assert len(kinds) == 1


def test_table_one_categorical_levels_are_nested_rows(cohort_frame):
    outcome = analyses.table_one(cohort_frame, ["sex"], group="nyha")
    rows = outcome.table["rows"]
    assert rows[0]["header"] is True
    levels = [row for row in rows if row.get("level")]
    assert {row["level"] for row in levels} == {"Female", "Male", "male"}


def test_table_one_labels_come_from_the_dictionary(cohort_frame):
    outcome = analyses.table_one(
        cohort_frame,
        ["age"],
        dictionary={"age": {"label": "Age", "unit": "years"}},
    )
    assert outcome.table["rows"][0]["label"] == "Age (years)"


def test_table_one_refuses_too_many_groups(cohort_frame):
    wide = cohort_frame.copy()
    wide["bucket"] = np.arange(len(wide)) % 9
    with pytest.raises(analyses.AnalysisError, match="more than 8"):
        analyses.table_one(wide, ["age"], group="bucket")


def test_compare_reports_estimate_before_p_value(two_group_frame):
    outcome = analyses.compare(two_group_frame, "lvef", group="sex")
    assert outcome.method == "compare"
    assert outcome.result["estimate"] is not None
    assert outcome.result["p_value"] is not None
    assert any(effect["name"] for effect in outcome.result["effect_sizes"])
    # Every result carries the diagnostics it was judged on.
    assert outcome.result["assumptions"]


def test_compare_values_are_publishable(two_group_frame):
    outcome = analyses.compare(two_group_frame, "lvef", group="sex")
    names = {value["name"] for value in outcome.values}
    assert "lvef:p" in names
    assert "lvef:estimate" in names
    for value in outcome.values:
        assert value["value"] is not None


def test_compare_refuses_a_non_numeric_outcome(two_group_frame):
    with pytest.raises(analyses.AnalysisError, match="not numeric"):
        analyses.compare(two_group_frame, "sex", group="nyha")


def test_compare_reports_nothing_for_a_single_observation_group(cohort_frame):
    """One row in a group is not a comparison: the result must say so, not invent a p."""
    outcome = analyses.compare(cohort_frame, "lvef", group="sex")
    assert outcome.result["p_value"] is None
    assert outcome.values == []
    assert any(
        "two or more observations" in warning for warning in outcome.result["warnings"]
    )


def test_multiplicity_is_named_and_ordered(cohort_frame):
    outcome = analyses.table_one(
        cohort_frame, ["age", "lvef"], group="nyha", adjust_method="bonferroni"
    )
    raw = [row["p"] for row in outcome.table["rows"] if row.get("p") is not None]
    adjusted = [
        row["p_adjusted"] for row in outcome.table["rows"] if row.get("p") is not None
    ]
    assert outcome.table["adjustment"] == "bonferroni"
    assert all(adj >= r - 1e-12 for r, adj in zip(raw, adjusted, strict=True))


def test_unknown_adjustment_is_a_client_error(cohort_frame):
    with pytest.raises(analyses.AnalysisError):
        analyses.table_one(cohort_frame, ["age"], group="nyha", adjust_method="magic")


# ---------------------------------------------------------------------------
# survival, diagnostic accuracy and 2x2 association (phase 5)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def survival_frame() -> pd.DataFrame:
    """Events happen immediately in one arm; the other is censored late.

    Deterministic on purpose: the log-rank test must be significant, one median is
    reached and the other is not, and nothing depends on a random draw.
    """
    return pd.DataFrame(
        {
            "time": [1.0] * 12 + [10.0] * 12,
            "event": [1] * 12 + [0] * 12,
            "arm": ["treated"] * 12 + ["control"] * 12,
        }
    )


def test_survival_reports_medians_and_a_log_rank_p(survival_frame):
    outcome = analyses.survival(survival_frame, time="time", event="event", group="arm")
    assert outcome.result["logrank"]["p_value"] is not None
    assert outcome.result["logrank"]["p_value"] < 0.05
    medians = {curve["label"]: curve["median"] for curve in outcome.result["curves"]}
    assert medians["treated"] == pytest.approx(1.0)
    assert medians["control"] is None  # survival never falls to 0.5: 'not reached'
    assert any("not reached" in row["cells"]["median"] for row in outcome.table["rows"])


def test_survival_keeps_a_step_curve_for_plotting(survival_frame):
    outcome = analyses.survival(survival_frame, time="time", event="event", group="arm")
    for curve in outcome.result["curves"]:
        assert len(curve["step"]) >= 2, curve
        # A Kaplan-Meier curve starts at S = 1 with everyone at risk.
        assert curve["step"][0] == [0.0, 1.0]
        assert all(0.0 <= point[1] <= 1.0 for point in curve["step"])
        assert [point[0] for point in curve["step"]] == sorted(
            point[0] for point in curve["step"]
        )
    # The arm with no event is a flat line at 1, not an empty series.
    control = next(
        curve for curve in outcome.result["curves"] if curve["label"] == "control"
    )
    assert {point[1] for point in control["step"]} == {1.0}


def test_survival_rejects_a_missing_or_mistyped_group(survival_frame):
    with pytest.raises(analyses.AnalysisError, match="grouping column 'nope'"):
        analyses.survival(survival_frame, time="time", event="event", group="nope")
    with pytest.raises(
        analyses.AnalysisError, match="cannot also be the follow-up time"
    ):
        analyses.survival(survival_frame, time="time", event="event", group="time")


def test_survival_accepts_a_text_event_indicator():
    frame = pd.DataFrame(
        {
            "months": [1.0, 2.0, 3.0, 9.0, 9.5, 10.0],
            "status": ["yes", "yes", "yes", "no", "no", "no"],
            "arm": ["a", "a", "a", "b", "b", "b"],
        }
    )
    outcome = analyses.survival(frame, time="months", event="status", group="arm")
    events = {curve["label"]: curve["events"] for curve in outcome.result["curves"]}
    assert events == {"a": 3, "b": 0}


def test_cox_presents_terms_in_the_requested_order():
    rng = np.random.default_rng(19)
    n = 180
    frame = pd.DataFrame(
        {
            "time": rng.exponential(20, n).round(2),
            "event": rng.choice([0, 1], n, p=[0.4, 0.6]),
            "arm": rng.choice(["control", "treatment"], n),
            "age": rng.normal(62, 9, n).round(),
        }
    )
    arms_first = analyses.cox(
        frame, time="time", event="event", covariates=["arm", "age"]
    )
    assert [row["cells"]["term"] for row in arms_first.table["rows"]] == [
        "arm_treatment",
        "age",
    ]
    age_first = analyses.cox(
        frame, time="time", event="event", covariates=["age", "arm"]
    )
    assert [row["cells"]["term"] for row in age_first.table["rows"]] == [
        "age",
        "arm_treatment",
    ]


def test_cox_reports_a_hazard_ratio_with_an_interval_and_a_p_value():
    rng = np.random.default_rng(23)
    n = 200
    frame = pd.DataFrame(
        {
            "time": rng.exponential(20, n).round(2),
            "event": rng.choice([0, 1], n),
            "arm": rng.choice(["control", "treatment"], n),
        }
    )
    outcome = analyses.cox(frame, time="time", event="event", covariates=["arm"])
    term = outcome.result["terms"][0]
    assert term["hr"] > 0
    assert term["ci_low"] <= term["hr"] <= term["ci_high"]
    assert 0.0 <= term["p"] <= 1.0
    names = {value["name"] for value in outcome.values}
    assert "cox:arm_treatment:hr" in names
    assert "cox:arm_treatment:p" in names


def test_cox_says_when_the_optional_diagnostics_are_absent():
    """lifelines is not a dependency, so the PH test is skipped — and the table says so."""
    rng = np.random.default_rng(29)
    n = 120
    frame = pd.DataFrame(
        {
            "time": rng.exponential(20, n),
            "event": rng.choice([0, 1], n),
            "arm": rng.choice(["control", "treatment"], n),
        }
    )
    outcome = analyses.cox(frame, time="time", event="event", covariates=["arm"])
    if outcome.result["ph_test"] is None:
        assert any("'survival' extra" in note for note in outcome.table["notes"])
    else:
        assert any("Grambsch-Therneau" in note for note in outcome.table["notes"])


def test_cox_needs_a_covariate_and_refuses_the_time_column_as_one(survival_frame):
    with pytest.raises(analyses.AnalysisError, match="at least one covariate"):
        analyses.cox(survival_frame, time="time", event="event", covariates=[])
    with pytest.raises(analyses.AnalysisError, match="cannot also be covariates"):
        analyses.cox(survival_frame, time="time", event="event", covariates=["time"])


@pytest.fixture(scope="module")
def diagnostic_frame() -> pd.DataFrame:
    """A test that separates the two outcome classes perfectly."""
    return pd.DataFrame(
        {"score": [0.9] * 20 + [0.1] * 20, "outcome": ["yes"] * 20 + ["no"] * 20}
    )


def test_diagnostic_reports_a_perfect_auc_and_the_confusion_at_the_cutoff(
    diagnostic_frame,
):
    outcome = analyses.diagnostic(
        diagnostic_frame, test="score", outcome="outcome", cutoff=0.5
    )
    assert outcome.result["auc"]["estimate"] == pytest.approx(1.0)
    assert outcome.result["accuracy"]["sensitivity"] == pytest.approx(1.0)
    assert outcome.result["accuracy"]["specificity"] == pytest.approx(1.0)
    assert outcome.result["confusion"] == {"tp": 20, "fp": 0, "fn": 0, "tn": 20}


def test_diagnostic_without_a_cutoff_says_it_chose_one_on_the_sample(diagnostic_frame):
    outcome = analyses.diagnostic(diagnostic_frame, test="score", outcome="outcome")
    assert outcome.result["cutoff"] == pytest.approx(0.9)
    assert any("optimistic" in note for note in outcome.table["notes"])


def test_diagnostic_states_the_prevalence_that_ppv_belongs_to():
    frame = pd.DataFrame(
        {"score": [0.9] * 30 + [0.1] * 60, "outcome": ["yes"] * 30 + ["no"] * 60}
    )
    outcome = analyses.diagnostic(frame, test="score", outcome="outcome", cutoff=0.5)
    assert any("prevalence" in note.lower() for note in outcome.table["notes"])


def test_diagnostic_refuses_a_three_level_outcome():
    frame = pd.DataFrame({"score": [0.1, 0.2, 0.3], "outcome": ["a", "b", "c"]})
    with pytest.raises(analyses.AnalysisError, match="exactly two levels"):
        analyses.diagnostic(frame, test="score", outcome="outcome")


def test_diagnostic_refuses_a_text_test_column():
    frame = pd.DataFrame({"score": ["x", "y", "z"], "outcome": ["yes", "no", "yes"]})
    with pytest.raises(analyses.AnalysisError, match="not numeric"):
        analyses.diagnostic(frame, test="score", outcome="outcome")


@pytest.fixture(scope="module")
def two_by_two_frame() -> pd.DataFrame:
    """a=30, b=10, c=10, d=50: RR 4.5 and OR 15 exactly."""
    pairs = (
        [("exposed", "yes")] * 30
        + [("exposed", "no")] * 10
        + [("unexposed", "yes")] * 10
        + [("unexposed", "no")] * 50
    )
    return pd.DataFrame(pairs, columns=["exposure", "outcome"])


def test_ratio_2x2_computes_the_measures_of_association(two_by_two_frame):
    outcome = analyses.ratio_2x2(
        two_by_two_frame, exposure="exposure", outcome="outcome"
    )
    assert outcome.result["relative_risk"] == pytest.approx(4.5)
    assert outcome.result["odds_ratio"] == pytest.approx(15.0)
    assert outcome.result["risk_difference"] == pytest.approx(0.75 - 10 / 60)
    assert outcome.n == 100


def test_ratio_2x2_orientation_is_explicit(two_by_two_frame):
    """'exposed' is compared against 'unexposed' — the reference is named in the result."""
    outcome = analyses.ratio_2x2(
        two_by_two_frame, exposure="exposure", outcome="outcome"
    )
    assert outcome.result["exposure_level"] == "exposed"
    assert outcome.result["reference_level"] == "unexposed"
    assert outcome.result["event_level"] == "yes"
    assert any("reference" in note for note in outcome.table["notes"])


def test_ratio_2x2_refuses_a_column_with_more_than_two_levels():
    frame = pd.DataFrame(
        {"exposure": ["a", "b", "c", "a"], "outcome": ["yes", "no", "yes", "no"]}
    )
    with pytest.raises(analyses.AnalysisError, match="exactly two levels"):
        analyses.ratio_2x2(frame, exposure="exposure", outcome="outcome")


def test_ratio_2x2_flags_the_haldane_correction_for_a_zero_cell():
    pairs = [("exposed", "yes")] * 10 + [("unexposed", "no")] * 10
    frame = pd.DataFrame(pairs, columns=["exposure", "outcome"])
    outcome = analyses.ratio_2x2(frame, exposure="exposure", outcome="outcome")
    assert outcome.result["haldane_applied"] is True
    assert any("Haldane" in note for note in outcome.table["notes"])


# ---------------------------------------------------------------------------
# logistic regression, Mantel-Haenszel, agreement
# ---------------------------------------------------------------------------


def test_logistic_reports_odds_ratios_and_names_the_event():
    rng = np.random.default_rng(53)
    n = 300
    frame = pd.DataFrame({"x": rng.normal(0, 1, n)})
    frame["y"] = np.where(frame["x"] > 0.3, "yes", "no")
    frame.loc[rng.choice(n, 30, replace=False), "y"] = rng.choice(["yes", "no"], 30)
    outcome = analyses.logistic(frame, outcome="y", covariates=["x"])
    term = outcome.result["terms"][0]
    assert term["or"] > 1  # higher x goes with the event
    assert term["ci_low"] <= term["or"] <= term["ci_high"]
    assert outcome.result["auc"] is not None
    assert any("event 'yes'" in note for note in outcome.table["notes"])


def test_logistic_refuses_a_three_level_outcome_and_an_empty_model():
    frame = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": ["a", "b", "c"]})
    with pytest.raises(analyses.AnalysisError, match="exactly two levels"):
        analyses.logistic(frame, outcome="y", covariates=["x"])
    with pytest.raises(analyses.AnalysisError, match="at least one covariate"):
        analyses.logistic(frame, outcome="y", covariates=[])


def test_logistic_refuses_the_outcome_as_a_covariate():
    frame = pd.DataFrame({"y": ["yes", "no", "yes", "no"]})
    with pytest.raises(analyses.AnalysisError, match="cannot also be a covariate"):
        analyses.logistic(frame, outcome="y", covariates=["y"])


@pytest.fixture(scope="module")
def stratified_frame() -> pd.DataFrame:
    """Two strata with the same association: exposed 3x the odds of the event."""
    rows = []
    for a, b, c, d in ((10, 10, 5, 15), (12, 8, 6, 14)):
        rows += (
            [("exposed", "yes")] * a
            + [("exposed", "no")] * b
            + [("unexposed", "yes")] * c
            + [("unexposed", "no")] * d
        )
    frame = pd.DataFrame(rows, columns=["exposure", "outcome"])
    frame["site"] = ["s1"] * 40 + ["s2"] * 40
    return frame


def test_mantel_haenszel_pools_the_strata(stratified_frame):
    outcome = analyses.mantel_haenszel(
        stratified_frame, exposure="exposure", outcome="outcome", stratum="site"
    )
    assert outcome.result["n_strata"] == 2
    # Both strata have an odds ratio near 3 ...
    assert outcome.result["or_mh"] == pytest.approx(3.24, rel=0.05)
    # ... and a risk ratio of exactly 2, because the outcome is common (50%). The odds
    # ratio overstating the risk ratio here is the reason the table reports both.
    assert outcome.result["rr_mh"] == pytest.approx(2.0, rel=0.05)
    assert outcome.result["or_mh"] > outcome.result["rr_mh"]
    assert outcome.result["mh_test"]["p_value"] < 0.05


def test_mantel_haenszel_orients_like_the_2x2_analysis(stratified_frame):
    """The same two columns must not give an odds ratio and its reciprocal in two places."""
    pooled = analyses.mantel_haenszel(
        stratified_frame, exposure="exposure", outcome="outcome", stratum="site"
    )
    crude = analyses.ratio_2x2(stratified_frame, exposure="exposure", outcome="outcome")
    assert pooled.result["or_mh"] == pytest.approx(crude.result["odds_ratio"], rel=0.15)
    assert any("compared with" in note for note in pooled.table["notes"])


def test_mantel_haenszel_needs_three_distinct_columns(stratified_frame):
    with pytest.raises(analyses.AnalysisError, match="three different columns"):
        analyses.mantel_haenszel(
            stratified_frame, exposure="exposure", outcome="outcome", stratum="exposure"
        )


def test_icc_close_to_one_for_agreeing_measurements():
    rng = np.random.default_rng(59)
    base = rng.normal(130, 15, 60).round(1)
    frame = pd.DataFrame({"a": base, "b": base + rng.normal(0, 1.5, 60).round(1)})
    outcome = analyses.agreement(frame, raters=["a", "b"], measure="icc")
    assert outcome.result["icc"] > 0.9
    assert outcome.result["model"] == "ICC(2,1)"
    assert "absolute agreement" in outcome.result["model_label"]
    assert outcome.result["n_subjects"] == 60


def test_bland_altman_reports_the_bias_and_its_limits():
    frame = pd.DataFrame({"a": [10, 12, 14, 16, 18, 20], "b": [10, 12, 14, 16, 18, 22]})
    outcome = analyses.agreement(frame, raters=["a", "b"], measure="bland_altman")
    assert outcome.result["bias"] == pytest.approx(-2 / 6)
    assert outcome.result["loa"][0] < outcome.result["loa"][1]
    assert 0.0 <= outcome.result["within_loa_pct"] <= 100.0
    assert any("a - b" in note for note in outcome.table["notes"])


def test_kappa_matches_its_definition():
    """po = 0.8, pe = 0.5 -> kappa = 0.6."""
    pairs = (
        [("yes", "yes")] * 20
        + [("yes", "no")] * 5
        + [("no", "yes")] * 5
        + [("no", "no")] * 20
    )
    frame = pd.DataFrame(pairs, columns=["r1", "r2"])
    outcome = analyses.agreement(frame, raters=["r1", "r2"], measure="kappa")
    assert outcome.result["observed_agreement"] == pytest.approx(0.8)
    assert outcome.result["expected_agreement"] == pytest.approx(0.5)
    assert outcome.result["kappa"] == pytest.approx(0.6)


def test_agreement_refuses_what_it_cannot_compare():
    frame = pd.DataFrame(
        {"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 3.0], "c": [1.0, 2.0, 3.0]}
    )
    with pytest.raises(
        analyses.AnalysisError, match="at least two measurement columns"
    ):
        analyses.agreement(frame, raters=["a"], measure="icc")
    with pytest.raises(analyses.AnalysisError, match="exactly two raters"):
        analyses.agreement(frame, raters=["a", "b", "c"], measure="kappa")
    with pytest.raises(analyses.AnalysisError, match="exactly two measurements"):
        analyses.agreement(frame, raters=["a", "b", "c"], measure="bland_altman")
    with pytest.raises(analyses.AnalysisError, match="unknown agreement measure"):
        analyses.agreement(frame, raters=["a", "b"], measure="nope")


# ---------------------------------------------------------------------------
# missing data: Little's MCAR and multiple imputation (phase 6)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def missing_frame() -> pd.DataFrame:
    """Complete data, then LVEF deleted at random and more often in the sickest class."""
    rng = np.random.default_rng(83)
    n = 240
    frame = pd.DataFrame(
        {
            "age": rng.normal(62, 9, n).round(),
            "lvef": rng.normal(48, 12, n).round(1),
            "nyha": rng.choice(["II", "III", "IV"], n),
            "arm": rng.choice(["control", "treatment"], n),
        }
    )
    frame["lvef"] += frame["nyha"].map({"II": 4.0, "III": 0.0, "IV": -6.0})
    frame["lvef"] += (frame["arm"] == "treatment") * 3.0
    deleted = rng.random(n) < np.where(frame["nyha"] == "IV", 0.5, 0.12)
    frame.loc[deleted, "lvef"] = np.nan
    return frame


def test_mcar_reports_the_test_and_the_patterns(missing_frame):
    outcome = analyses.mcar(missing_frame, variables=["age", "lvef"])
    assert outcome.result["df"] >= 1
    assert 0.0 <= outcome.result["p_value"] <= 1.0
    assert outcome.result["variables"] == ["age", "lvef"]
    assert outcome.table["rows"][0]["cells"]["column"].startswith("chi-square")
    # The missingness of the column itself is listed after the test row.
    assert any(
        row["cells"]["column"].startswith("lvef") for row in outcome.table["rows"][1:]
    )


def test_mcar_says_that_not_rejecting_is_not_proof(missing_frame):
    """Little's test has low power: the text must not turn 'p > 0.05' into 'MCAR'."""
    outcome = analyses.mcar(missing_frame, variables=["age", "lvef"])
    assert any("does not prove" in note for note in outcome.table["notes"])
    assert any(
        "MCAR is a property of the mechanism" in note for note in outcome.table["notes"]
    )


def test_mcar_needs_two_numeric_columns_and_some_missing_values():
    frame = pd.DataFrame(
        {"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 3.0], "c": ["x", "y", "z"]}
    )
    with pytest.raises(analyses.AnalysisError, match="at least two numeric"):
        analyses.mcar(frame, variables=["a", "c"])
    with pytest.raises(analyses.AnalysisError, match=r"nothing to test|no missing"):
        analyses.mcar(frame, variables=["a", "b"])


def test_multiple_imputation_pools_a_mean_difference(missing_frame):
    outcome = analyses.multiple_imputation(
        missing_frame,
        target="compare",
        outcome="lvef",
        group="arm",
        m=5,
        maxit=5,
        seed=101,
    )
    assert outcome.result["m"] == 5
    assert outcome.result["imputed"] == {
        "lvef": int(missing_frame["lvef"].isna().sum())
    }
    assert outcome.values, "a pooled estimate must be publishable"
    term = outcome.result["terms"][0]
    assert term["fmi"] >= 0
    assert 0.0 <= term["p_value"] <= 1.0
    # The complete case is shown next to the pooled one.
    assert any(c["key"] == "cc_estimate" for c in outcome.table["columns"])


def test_multiple_imputation_is_reproducible_with_a_seed(missing_frame):
    """The same seed must give the same pooled estimate, or a reported number is not reproducible."""
    first = analyses.multiple_imputation(
        missing_frame,
        target="compare",
        outcome="lvef",
        group="arm",
        m=3,
        maxit=3,
        seed=7,
    )
    second = analyses.multiple_imputation(
        missing_frame,
        target="compare",
        outcome="lvef",
        group="arm",
        m=3,
        maxit=3,
        seed=7,
    )
    assert first.result["terms"][0]["estimate"] == pytest.approx(
        second.result["terms"][0]["estimate"], rel=0, abs=0
    )


def test_multiple_imputation_recovers_the_complete_data_answer(missing_frame):
    """A sanity check on correctness, not on shape: under MCAR the pooled estimate must
    land near the one the complete data would have given."""
    complete = missing_frame["lvef"].fillna(
        missing_frame["lvef"].groupby(missing_frame["nyha"]).transform("median")
    )
    truth = analyses.compare(
        missing_frame.assign(lvef=complete), "lvef", group="arm", kind="welch"
    ).result["estimate"]
    pooled = analyses.multiple_imputation(
        missing_frame,
        target="compare",
        outcome="lvef",
        group="arm",
        m=10,
        maxit=5,
        seed=3,
    )
    estimate = pooled.result["terms"][0]["estimate"]
    standard_error = pooled.result["terms"][0]["se"]
    assert abs(estimate - truth) < 3 * max(standard_error, 1e-6)


def test_multiple_imputation_pools_a_logistic_model(missing_frame):
    rng = np.random.default_rng(91)
    frame = missing_frame.copy()
    linear = -3.0 + 0.05 * frame["lvef"] + 0.02 * frame["age"]
    frame["died"] = np.where(
        rng.random(len(frame)) < 1 / (1 + np.exp(-linear)), "yes", "no"
    )
    outcome = analyses.multiple_imputation(
        frame,
        target="logistic",
        outcome="died",
        covariates=["age", "lvef"],
        m=3,
        maxit=3,
        seed=5,
    )
    terms = {row["cells"]["term"] for row in outcome.table["rows"]}
    assert {"age", "lvef"} <= terms
    assert "(Intercept)" in terms
    # The intercept is shown but is not an effect to publish.
    assert not any(value["name"] == "mi:const" for value in outcome.values)


def test_multiple_imputation_refuses_an_omnibus_comparison(missing_frame):
    """Pooling needs an estimate with a standard error; a 3-group ANOVA has none."""
    with pytest.raises(analyses.AnalysisError, match="two-group column"):
        analyses.multiple_imputation(
            missing_frame, target="compare", outcome="lvef", group="nyha", m=3, maxit=3
        )


def test_multiple_imputation_refuses_when_nothing_is_missing():
    rng = np.random.default_rng(97)
    frame = pd.DataFrame(
        {
            "lvef": rng.normal(48, 12, 60),
            "arm": rng.choice(["control", "treatment"], 60),
            "age": rng.normal(62, 9, 60),
        }
    )
    with pytest.raises(analyses.AnalysisError, match="nothing to impute"):
        analyses.multiple_imputation(
            frame, target="compare", outcome="lvef", group="arm"
        )


def test_multiple_imputation_needs_at_least_two_imputations(missing_frame):
    with pytest.raises(analyses.AnalysisError, match="at least two imputations"):
        analyses.multiple_imputation(
            missing_frame, target="compare", outcome="lvef", group="arm", m=1
        )
