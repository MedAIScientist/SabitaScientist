"""The analyses a cohort study reports: description, Table 1, group comparison.

Every function here is pure: it takes a frame (already restricted to the analysis
population) and returns a serialisable result. Nothing touches the database, so the
same code can move to a worker process unchanged.

Three rules the output obeys, because a biostatistician is the reader:

* an estimate comes with its confidence interval before its p-value;
* assumption checks are diagnostics, never gates — the test runs anyway and the
  result says what was checked;
* a multiplicity correction is always named, and the raw p-value is kept next to it.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from .vendor.biostats._types import CI
from .vendor.biostats.agreement import bland_altman
from .vendor.biostats.contingency import (
    TwoByTwo,
    analyze_twobytwo,
    detect_event_level,
    detect_reference_level,
)
from .vendor.biostats.diagnostic import confusion_at, delong_auc, diagnostic_accuracy
from .vendor.biostats.effect_sizes import cramers_v
from .vendor.biostats.inference import compare_groups, groups_from_frame
from .vendor.biostats.mcar import littles_mcar_test
from .vendor.biostats.mi import ImputationSpec, analyze_mi, impute
from .vendor.biostats.mi.report import missingness_summary
from .vendor.biostats.multiplicity import adjust, normalize_method
from .vendor.biostats.normality import normality_check
from .vendor.biostats.rates import mantel_haenszel as mantel_haenszel_vendor
from .vendor.biostats.references import REFERENCES as METHOD_REFERENCES
from .vendor.biostats.regression import logistic_regression
from .vendor.biostats.reliability import cohens_kappa, icc
from .vendor.biostats.survival import compare_survival, cox_regression

__all__ = [
    "ENGINE_VERSION",
    "AnalysisError",
    "AnalysisOutcome",
    "agreement",
    "compare",
    "cox",
    "descriptive",
    "diagnostic",
    "logistic",
    "mantel_haenszel",
    "mcar",
    "multiple_imputation",
    "ratio_2x2",
    "survival",
    "table_one",
]

ENGINE_VERSION = "cohort-engine/1"

_ADJUSTMENTS = ("holm", "fdr_bh", "bonferroni", "none")
_MAX_GROUP_LEVELS = 8
_MIN_LEVEL_COUNT = 1


class AnalysisError(ValueError):
    """The requested analysis cannot be run on this population."""


class AnalysisOutcome:
    """What an analysis produced, in the three shapes the rest of the app needs."""

    __slots__ = ("method", "n", "result", "table", "values")

    def __init__(
        self,
        method: str,
        n: int,
        result: dict[str, Any],
        *,
        table: dict[str, Any] | None = None,
        values: list[dict[str, Any]] | None = None,
    ) -> None:
        self.method = method
        self.n = n
        self.result = result
        self.table = table
        self.values = values or []


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise AnalysisError(f"column '{column}' is not in this version")
    series = frame[column]
    if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        raise AnalysisError(f"column '{column}' is not numeric ({series.dtype})")
    return series.astype(float)


def _categorical(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise AnalysisError(f"column '{column}' is not in this version")
    return frame[column]


def _label(dictionary: dict[str, Any], column: str) -> str:
    entry = (dictionary or {}).get(column) or {}
    label = str(entry.get("label") or "").strip()
    unit = str(entry.get("unit") or "").strip()
    if label and unit:
        return f"{label} ({unit})"
    return label or column


def _fmt(value: float | None, digits: int = 1) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "–"
    return f"{value:.{digits}f}"


def _fmt_p(p: float | None) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "–"
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


def _p_phrase(p: float | None) -> str:
    """'p < 0.001' or 'p = 0.032' — an inequality must not be written as an equality."""
    text = _fmt_p(p)
    return text if text in ("–", "<0.001") else f"= {text}"


def _p_value(p: float | None) -> str:
    return "–" if p is None else (f"{p:.4g}" if p >= 0.001 else "<0.001")


def _adjust_method(method: str | None) -> str:
    try:
        name = normalize_method(method or "holm")
    except ValueError as exc:
        raise AnalysisError(str(exc)) from exc
    if name not in {normalize_method(m) for m in _ADJUSTMENTS}:
        raise AnalysisError(
            f"unknown multiplicity correction {method!r}; expected one of {', '.join(_ADJUSTMENTS)}"
        )
    return name


def _natural_key(value: str) -> tuple:
    """Sort 'II' before 'III' before 'IV' and '2' before '10' in a group column."""
    parts = re.split(r"(\d+)", str(value).casefold())
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part) for part in parts if part
    )


def _levels(series: pd.Series, name: str) -> list[str]:
    """Observed levels of a grouping column, in natural (ordinal-friendly) order."""
    clean = series.dropna()
    if clean.empty:
        raise AnalysisError(f"grouping column '{name}' has no observed values")
    levels = sorted({str(v) for v in clean}, key=_natural_key)
    if len(levels) < 2:
        raise AnalysisError(
            f"grouping column '{name}' has a single level ({levels[0]!r})"
        )
    if len(levels) > _MAX_GROUP_LEVELS:
        raise AnalysisError(
            f"grouping column '{name}' has {len(levels)} levels; "
            f"a table over more than {_MAX_GROUP_LEVELS} groups is unreadable"
        )
    return levels


def _effect_payload(effect: Any) -> dict[str, Any] | None:
    if effect is None:
        return None
    estimate = getattr(effect, "estimate", None)
    if estimate is None or (isinstance(estimate, float) and np.isnan(estimate)):
        return None
    ci = getattr(effect, "ci", None)
    return {
        "name": effect.name,
        "estimate": float(estimate),
        "ci": [float(ci.lower), float(ci.upper)] if ci is not None else None,
        "magnitude": effect.magnitude() if hasattr(effect, "magnitude") else "",
        "note": getattr(effect, "note", ""),
    }


def _categorical_test(table: np.ndarray) -> tuple[float | None, str, list[str]]:
    """Pearson chi-square, or Fisher's exact test for a 2x2 with small counts."""
    warnings: list[str] = []
    table = table[:, table.sum(axis=0) > 0]
    table = table[table.sum(axis=1) > 0, :]
    if table.shape[0] < 2 or table.shape[1] < 2:
        return (
            None,
            "not testable (a single row or column)",
            ["a level is present in one group only"],
        )
    if table.shape == (2, 2) and int(table.sum()) <= 200:
        _, p = stats.fisher_exact(table)
        return float(p), "Fisher's exact test", warnings
    expected = stats.contingency.expected_freq(table)
    small = float((expected < 5).mean())
    if small > 0:
        warnings.append(
            f"{small:.0%} of expected counts are below 5: the chi-square approximation is rough"
        )
    try:
        _, p, _, _ = stats.chi2_contingency(table, correction=False)
    except ValueError as exc:  # a degenerate table
        return None, "not testable", [*warnings, str(exc)]
    return float(p), "Pearson chi-square (no continuity correction)", warnings


# ---------------------------------------------------------------------------
# descriptive statistics
# ---------------------------------------------------------------------------


def _numeric_stats(series: pd.Series, *, summary: str) -> dict[str, Any]:
    observed = series.dropna()
    out: dict[str, Any] = {
        "n": int(observed.size),
        "missing": int(series.isna().sum()),
    }
    if observed.empty:
        out["cell"] = "–"
        return out
    sd = float(observed.std(ddof=1)) if observed.size > 1 else float("nan")
    q1, median, q3 = (float(v) for v in observed.quantile([0.25, 0.5, 0.75]))
    mean = float(observed.mean())
    out.update(
        mean=mean,
        sd=sd,
        median=median,
        q1=q1,
        q3=q3,
        min=float(observed.min()),
        max=float(observed.max()),
    )
    normal = True
    if observed.size >= 3:
        check = normality_check(observed, "normality", alpha=0.05)
        out["normality"] = {
            "p": check.p_value,
            "status": check.status,
            "detail": check.detail,
        }
        normal = check.status != "violated"
    style = (
        "mean"
        if summary == "mean"
        else ("median" if summary == "median" else ("mean" if normal else "median"))
    )
    out["summary"] = style
    out["cell"] = (
        f"{_fmt(mean)} ({_fmt(sd)})"
        if style == "mean"
        else f"{_fmt(median)} [{_fmt(q1)}–{_fmt(q3)}]"
    )
    return out


def descriptive(
    frame: pd.DataFrame,
    variables: list[str],
    *,
    dictionary: dict[str, Any] | None = None,
    summary: str = "auto",
) -> AnalysisOutcome:
    """One row per variable: how many were measured, and what they look like."""
    if not variables:
        raise AnalysisError("at least one variable is needed")
    dictionary = dictionary or {}
    rows: list[dict[str, Any]] = []
    notes = [
        "Each variable is described on the rows where it was measured "
        "(available-case description, not a complete-case analysis)."
    ]
    for column in variables:
        if column not in frame.columns:
            raise AnalysisError(f"column '{column}' is not in this version")
        series = frame[column]
        label = _label(dictionary, column)
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(
            series
        ):
            stats_block = _numeric_stats(series.astype(float), summary=summary)
            if stats_block.get("normality", {}).get("status") == "violated":
                notes.append(
                    f"'{column}' departs from normality (Shapiro–Wilk p = "
                    f"p {_p_phrase(stats_block['normality']['p'])}): its median and IQR are reported."
                )
            rows.append(
                {
                    "label": label,
                    "column": column,
                    "kind": "numeric",
                    "cell": stats_block.get("cell", "–"),
                    "stats": stats_block,
                    "missing": stats_block["missing"],
                    "n": stats_block["n"],
                }
            )
            continue

        observed = series.dropna().astype(str)
        counts = observed.value_counts().reindex(
            sorted(observed.unique(), key=_natural_key)
        )
        levels = [
            {
                "level": str(level),
                "n": int(count),
                "percent": round(100.0 * count / max(len(frame), 1), 1),
            }
            for level, count in counts.items()
            if count >= _MIN_LEVEL_COUNT
        ]
        rows.append(
            {
                "label": label,
                "column": column,
                "kind": "categorical",
                "cell": f"{len(levels)} level(s)",
                "stats": {
                    "n": int(observed.size),
                    "missing": int(series.isna().sum()),
                    "levels": levels,
                },
                "missing": int(series.isna().sum()),
                "n": int(observed.size),
            }
        )

    table = {
        "columns": ["Variable", "Value", "Missing"],
        "rows": [
            {
                "label": row["label"],
                "value": (
                    row["cell"]
                    if row["kind"] == "numeric"
                    else "; ".join(
                        f"{lv['level']}: {lv['n']} ({lv['percent']}%)"
                        for lv in row["stats"]["levels"]
                    )
                ),
                "missing": row["missing"],
                "kind": row["kind"],
                "detail": row,
            }
            for row in rows
        ],
        "notes": notes,
    }
    values: list[dict[str, Any]] = []
    for row in rows:
        block = row["stats"]
        if row["kind"] != "numeric" or block.get("mean") is None:
            continue
        values.append(
            {
                "name": f"{row['column']}:mean",
                "label": f"Mean ({row['label']})",
                "value": float(block["mean"]),
                "n": block["n"],
            }
        )
        values.append(
            {
                "name": f"{row['column']}:median",
                "label": f"Median ({row['label']})",
                "value": float(block["median"]),
                "n": block["n"],
            }
        )
    return AnalysisOutcome(
        method="descriptive",
        n=len(frame),
        result={"variables": len(variables), "rows": len(frame), "summary": summary},
        table=table,
        values=values,
    )


# ---------------------------------------------------------------------------
# Table 1
# ---------------------------------------------------------------------------


def table_one(
    frame: pd.DataFrame,
    variables: list[str],
    *,
    group: str | None = None,
    dictionary: dict[str, Any] | None = None,
    summary: str = "auto",
    adjust_method: str = "holm",
    alpha: float = 0.05,
) -> AnalysisOutcome:
    """The first table of a clinical paper: description by group, with a p-value.

    The p-values describe the sample; they are not adjusted for confounding, and the
    table says so. ``adjust_method`` corrects across the variables of the table.
    """
    if not variables:
        raise AnalysisError("at least one variable is needed")
    dictionary = dictionary or {}
    method = _adjust_method(adjust_method)
    levels = _levels(_categorical(frame, group), group) if group else []

    columns: list[dict[str, Any]] = [
        {"key": "overall", "label": f"All (n = {len(frame):,})"}
    ]
    for level in levels:
        n_level = int((frame[group].astype(str) == level).sum())
        columns.append({"key": f"g:{level}", "label": f"{level} (n = {n_level:,})"})
    if group:
        columns.append({"key": "p", "label": "p"})

    def _cells(series: pd.Series, block: dict[str, Any]) -> dict[str, str]:
        """One cell per column: the overall summary, then the same summary per group.

        The summary style is decided ONCE for the variable (from its overall
        distribution) and then used for every group. Deciding it per group would print
        a mean in one column and a median in the next, in the same row.
        """
        style = block.get("summary") or "mean"
        cells: dict[str, str] = {"overall": block.get("cell", "–")}
        for level in levels:
            part = series[frame[group].astype(str) == level].astype(float)
            cells[f"g:{level}"] = _numeric_stats(part, summary=style).get("cell", "–")
        return cells

    rows: list[dict[str, Any]] = []
    pending: list[
        tuple[int, float | None]
    ] = []  # (row index, raw p) for the correction
    notes = [
        "Table 1 describes the analysis population; each variable uses the rows where it was "
        "measured (available cases).",
        "p-values describe this sample. They are not adjusted for confounding and do not "
        "establish an effect.",
    ]
    if method != "none":
        notes.append(
            f"p-values are corrected for multiple testing across the {len(variables)} variable(s) "
            f"of this table with {method.upper()}; the raw value is shown next to it."
        )

    for column in variables:
        if column not in frame.columns:
            raise AnalysisError(f"column '{column}' is not in this version")
        series = frame[column]
        label = _label(dictionary, column)
        numeric = pd.api.types.is_numeric_dtype(
            series
        ) and not pd.api.types.is_bool_dtype(series)

        if numeric:
            block = _numeric_stats(series.astype(float), summary=summary)
            p_raw: float | None = None
            effect: dict[str, Any] | None = None
            test_name = ""
            warnings: list[str] = []
            if group:
                groups = groups_from_frame(frame, group, column, levels=levels)
                groups = {k: v for k, v in groups.items() if len(v) > 0}
                if len(groups) >= 2:
                    test = compare_groups(groups, kind="welch", alpha=alpha)
                    p_raw = test.p_value
                    test_name = test.name
                    effect = _effect_payload(test.primary_effect)
                    warnings = list(test.warnings)
            rows.append(
                {
                    "label": label,
                    "column": column,
                    "kind": "numeric",
                    "cells": _cells(series, block),
                    "stats": {"overall": block},
                    "n": block["n"],
                    "missing": block["missing"],
                    "p": p_raw,
                    "test": test_name,
                    "effect": effect,
                    "warnings": warnings,
                }
            )
            pending.append((len(rows) - 1, p_raw))
            continue

        obs = series.dropna().astype(str)
        counts = obs.value_counts().reindex(sorted(obs.unique(), key=_natural_key))
        p_raw = None
        effect = None
        test_name = ""
        warnings = []
        if group:
            subset = frame[[column, group]].dropna()
            table = pd.crosstab(subset[column].astype(str), subset[group].astype(str))
            table = table.reindex(index=counts.index, columns=levels, fill_value=0)
            p_raw, test_name, warnings = _categorical_test(table.to_numpy())
            try:
                effect = _effect_payload(cramers_v(table.to_numpy(), n_boot=200))
            except Exception:
                effect = None
        rows.append(
            {
                "label": label,
                "column": column,
                "kind": "categorical",
                "header": True,
                "cells": {"overall": "", **{f"g:{lv}": "" for lv in levels}},
                "stats": {
                    "overall": {"n": int(obs.size), "missing": int(series.isna().sum())}
                },
                "n": int(obs.size),
                "missing": int(series.isna().sum()),
                "p": p_raw,
                "test": test_name,
                "effect": effect,
                "warnings": warnings,
            }
        )
        pending.append((len(rows) - 1, p_raw))
        for level, count in counts.items():
            if count < _MIN_LEVEL_COUNT:
                continue
            cells = {
                "overall": f"{int(count)} ({100.0 * count / max(len(frame), 1):.1f}%)",
            }
            for lv in levels:
                mask = frame[group].astype(str) == lv
                part = int(((frame[column].astype(str) == level) & mask).sum())
                size = int(mask.sum())
                cells[f"g:{lv}"] = (
                    f"{part} ({100.0 * part / size:.1f}%)" if size else "0 (0.0%)"
                )
            rows.append(
                {
                    "label": f"    {level}",
                    "column": column,
                    "kind": "categorical",
                    "level": str(level),
                    "cells": cells,
                    "n": int(count),
                    "missing": 0,
                    "p": None,
                    "effect": None,
                    "warnings": [],
                }
            )

    if group and pending:
        adjusted = adjust([p for _, p in pending], method=method, alpha=alpha)
        for (row_index, raw), adj in zip(pending, adjusted, strict=True):
            if raw is None:
                continue
            rows[row_index]["p_adjusted"] = None if np.isnan(adj) else float(adj)
            rows[row_index]["adjustment"] = method
            if rows[row_index]["cells"].get("p") is None:
                rows[row_index]["cells"]["p"] = _fmt_p(
                    None if np.isnan(adj) else float(adj)
                )

    table = {
        "columns": columns,
        "rows": rows,
        "notes": notes,
        "adjustment": method if group else None,
        "group": group,
        "summary": summary,
    }
    return AnalysisOutcome(
        method="table1",
        n=len(frame),
        result={
            "group": group,
            "groups": levels,
            "variables": variables,
            "adjustment": method if group else None,
            "rows": len(frame),
        },
        table=table,
        values=[
            {
                "name": f"table1:{row['column']}:{'level' if row.get('level') else 'p'}",
                "label": row["label"].strip(),
                "value": float(row["p_adjusted"])
                if row.get("p_adjusted") is not None
                else (float(row["p"]) if row.get("p") is not None else None),
                "p_value": row.get("p_adjusted")
                if row.get("p_adjusted") is not None
                else row.get("p"),
                "n": row.get("n"),
            }
            for row in rows
            if row.get("p") is not None
        ],
    )


# ---------------------------------------------------------------------------
# two-group / multi-group comparison of one outcome
# ---------------------------------------------------------------------------


def compare(
    frame: pd.DataFrame,
    outcome: str,
    *,
    group: str,
    kind: str = "auto",
    alpha: float = 0.05,
    dictionary: dict[str, Any] | None = None,
) -> AnalysisOutcome:
    """Compare ``outcome`` across the levels of ``group``, estimate first."""
    dictionary = dictionary or {}
    _numeric(
        frame, outcome
    )  # validates that the outcome is numeric before anything else
    levels = _levels(_categorical(frame, group), group)
    groups = groups_from_frame(frame, group, outcome, levels=levels)
    groups = {k: v for k, v in groups.items() if len(v) > 0}
    if len(groups) < 2:
        raise AnalysisError(
            f"'{outcome}' has values in fewer than two groups of '{group}'; nothing to compare"
        )
    result = compare_groups(groups, kind=kind, alpha=alpha)
    result = result.model_dump()
    payload = _outcome_values(result, outcome, group, dictionary)
    table = {
        "columns": ["Group", "n", "Missing", "Mean (SD)", "Median [IQR]"],
        "rows": [
            {
                "label": str(level),
                "n": len(values),
                "missing": int(
                    frame.loc[frame[group].astype(str) == str(level), outcome]
                    .isna()
                    .sum()
                ),
                "mean_sd": f"{_fmt(float(np.mean(values)))} ({_fmt(float(np.std(values, ddof=1)))})"
                if len(values) > 1
                else _fmt(float(np.mean(values))),
                "median_iqr": _median_iqr(values),
            }
            for level, values in groups.items()
        ],
        "notes": [
            f"Outcome: {_label(dictionary, outcome)}; grouping: {group}.",
            "The test follows the Welch-first policy: unequal variances are the default "
            "assumption, and normality is reported as a diagnostic rather than used to choose "
            "the test.",
        ],
        "test": result,
    }
    return AnalysisOutcome(
        method="compare",
        n=int(sum(len(v) for v in groups.values())),
        result=result,
        table=table,
        values=payload,
    )


def _median_iqr(values: np.ndarray) -> str:
    if len(values) < 2:
        return _fmt(float(values[0])) if len(values) else "–"
    q1, median, q3 = (float(v) for v in np.percentile(values, [25, 50, 75]))
    return f"{_fmt(median)} [{_fmt(q1)}–{_fmt(q3)}]"


def _outcome_values(
    result: dict[str, Any], outcome: str, group: str, dictionary: dict[str, Any]
) -> list[dict[str, Any]]:
    """The publishable numbers of a comparison."""
    label = _label(dictionary, outcome)
    values: list[dict[str, Any]] = []
    p = result.get("p_value")
    p_adj = result.get("p_adjusted")
    if p is not None:
        values.append(
            {
                "name": f"{outcome}:p",
                "label": f"p-value ({label} by {group})",
                "value": float(p),
                "p_value": float(p),
                "n": sum(result.get("n_per_group") or []),
            }
        )
    if p_adj is not None:
        values.append(
            {
                "name": f"{outcome}:p_adjusted",
                "label": f"Adjusted p-value ({label} by {group})",
                "value": float(p_adj),
                "p_value": float(p_adj),
                "n": sum(result.get("n_per_group") or []),
            }
        )
    estimate = result.get("estimate")
    if estimate is not None:
        ci = result.get("estimate_ci") or {}
        values.append(
            {
                "name": f"{outcome}:estimate",
                "label": f"{result.get('estimate_label') or 'Estimate'} ({label})",
                "value": float(estimate),
                "ci_low": ci.get("lower"),
                "ci_high": ci.get("upper"),
                "n": sum(result.get("n_per_group") or []),
            }
        )
    for effect in result.get("effect_sizes") or []:
        if effect.get("estimate") is None:
            continue
        ci = effect.get("ci") or {}
        values.append(
            {
                "name": f"{outcome}:{effect.get('kind') or 'effect'}",
                "label": f"{effect.get('name')} ({label} by {group})",
                "value": float(effect["estimate"]),
                "ci_low": ci.get("lower"),
                "ci_high": ci.get("upper"),
                "n": sum(result.get("n_per_group") or []),
            }
        )
    return values


# ---------------------------------------------------------------------------
# time-to-event, diagnostic accuracy, 2x2 association
# ---------------------------------------------------------------------------

_MAX_CURVE_POINTS = 300


def _ci_text(ci: Any, digits: int = 2) -> str:
    if ci is None:
        return ""
    return f"{ci.lower:.{digits}f}–{ci.upper:.{digits}f}"


def _ci_pair(ci: Any) -> tuple[float | None, float | None]:
    if ci is None:
        return None, None
    return float(ci.lower), float(ci.upper)


def _downsample(times: np.ndarray, survival: np.ndarray) -> list[list[float]]:
    """A step curve is JSON-heavy; keep evenly spaced points plus the last one."""
    if len(times) <= _MAX_CURVE_POINTS:
        index = np.arange(len(times))
    else:
        index = np.unique(np.linspace(0, len(times) - 1, _MAX_CURVE_POINTS).astype(int))
    return [[float(times[i]), float(survival[i])] for i in index]


def survival(
    frame: pd.DataFrame,
    *,
    time: str,
    event: str,
    group: str | None = None,
    alpha: float = 0.05,
) -> AnalysisOutcome:
    """Kaplan-Meier curves, median survival per group, and the log-rank test."""
    if not time or not event:
        raise AnalysisError(
            "a survival analysis needs a follow-up time column and an event column"
        )
    for column, role in ((time, "time"), (event, "event")):
        if column not in frame.columns:
            raise AnalysisError(f"the {role} column '{column}' is not in this version")
    if group and group not in frame.columns:
        raise AnalysisError(f"the grouping column '{group}' is not in this version")
    if group and group in (time, event):
        raise AnalysisError(
            "the grouping column cannot also be the follow-up time or the event indicator"
        )
    covariates = [time, event] + ([group] if group else [])
    data = frame[covariates].dropna()
    if data.empty:
        raise AnalysisError("no row has both a follow-up time and an event indicator")
    try:
        comparison = compare_survival(data, time, event, group, alpha=alpha)
    except Exception as exc:
        raise AnalysisError(f"the survival model could not be fitted: {exc}") from exc

    rows: list[dict[str, Any]] = [
        {
            "label": curve.label,
            "kind": "survival",
            "cells": {
                "group": curve.label,
                "n": str(curve.n),
                "events": str(curve.events),
                "median": _fmt(curve.median, 2)
                if curve.median is not None
                else "not reached",
            },
        }
        for curve in comparison.curves
    ]
    columns = [
        {"key": "group", "label": "Group"},
        {"key": "n", "label": "n"},
        {"key": "events", "label": "Events"},
        {"key": "median", "label": "Median follow-up to event"},
    ]
    if comparison.logrank_p is not None:
        rows.append(
            {
                "label": "Log-rank test",
                "kind": "survival",
                "cells": {
                    "group": f"chi-square = {comparison.logrank_statistic:.3f}, df = {comparison.logrank_df}",
                    "n": "",
                    "events": "",
                    "median": f"p {_p_phrase(comparison.logrank_p)}",
                },
            }
        )
    notes = [
        "Follow-up times must be in the same unit; the event indicator is 1 = event, 0 = censored "
        "(text values 'yes'/'no', 'dead' and 'event' are read the same way).",
        "The confidence band is Greenwood's, on the log(-log S) scale; the median is 'not reached' "
        "when survival never falls to 0.5.",
    ]
    if group:
        notes.append(
            "The log-rank test compares the groups without adjusting for covariates."
        )
    if comparison.warnings:
        notes.extend(comparison.warnings)

    # A group with no event has no step from statsmodels, but a plot still needs a line:
    # S(t) = 1 across the follow-up. Say that with two points rather than nothing.
    last_followup = float(data[time].max())
    by_group = (
        {
            str(key): float(part[time].max())
            for key, part in data.groupby(group, observed=True)
        }
        if group
        else {}
    )

    def _step(curve: Any) -> list[list[float]]:
        """The step function a plot needs: it starts at (0, 1) and ends at the last point."""
        step = _downsample(curve.times, curve.survival)
        if not step:
            end = by_group.get(curve.label, last_followup)
            return [[0.0, 1.0], [end, 1.0]]
        if step[0][0] > 0:
            # Kaplan-Meier starts at S = 1 with everyone at risk; the estimator only lists
            # the times at which something happened.
            step.insert(0, [0.0, 1.0])
        return step

    values: list[dict[str, Any]] = []
    for curve in comparison.curves:
        if curve.median is not None:
            values.append(
                {
                    "name": f"{time}:median:{curve.label}",
                    "label": f"Median survival, {curve.label}",
                    "value": float(curve.median),
                    "n": curve.n,
                }
            )
    if comparison.logrank_p is not None:
        values.append(
            {
                "name": f"{time}:logrank_p",
                "label": f"Log-rank p ({time} by {group or 'all'})",
                "value": float(comparison.logrank_p),
                "p_value": float(comparison.logrank_p),
                "n": sum(curve.n for curve in comparison.curves),
            }
        )
    return AnalysisOutcome(
        method="survival",
        n=int(sum(curve.n for curve in comparison.curves)),
        result={
            "time": time,
            "event": event,
            "group": group,
            "curves": [
                {
                    "label": curve.label,
                    "n": curve.n,
                    "events": curve.events,
                    "median": curve.median,
                    "step": _step(curve),
                }
                for curve in comparison.curves
            ],
            "logrank": {
                "statistic": comparison.logrank_statistic,
                "df": comparison.logrank_df,
                "p_value": comparison.logrank_p,
            },
            "warnings": comparison.warnings,
            "references": comparison.references,
        },
        table={"columns": columns, "rows": rows, "notes": notes},
        values=values,
    )


def _order_terms(table: pd.DataFrame, covariates: list[str]) -> pd.DataFrame:
    """Present the terms in the order the covariates were requested.

    The design matrix puts numeric covariates first and then the dummies of each
    factor; that ordering matters for pooling across imputations, so it is kept in the
    model, but a table reads better in the order the user asked for.
    """
    terms = [str(term) for term in table["term"]]
    ordered: list[str] = []
    for covariate in covariates:
        for term in terms:
            if term in ordered:
                continue
            if term == covariate or term.startswith(f"{covariate}_"):
                ordered.append(term)
    for (
        term
    ) in terms:  # anything the loop could not attribute keeps its place at the end
        if term not in ordered:
            ordered.append(term)
    return table.set_index("term").loc[ordered].reset_index()


def cox(
    frame: pd.DataFrame,
    *,
    time: str,
    event: str,
    covariates: list[str],
    alpha: float = 0.05,
) -> AnalysisOutcome:
    """Cox proportional hazards: a hazard ratio with its interval per term."""
    if not time or not event:
        raise AnalysisError(
            "a Cox model needs a follow-up time column and an event column"
        )
    if not covariates:
        raise AnalysisError("a Cox model needs at least one covariate")
    needed = [time, event, *covariates]
    missing = [column for column in needed if column not in frame.columns]
    if missing:
        raise AnalysisError("not in this version: " + ", ".join(missing))
    if time in covariates or event in covariates:
        raise AnalysisError("the time and event columns cannot also be covariates")
    data = frame[needed].dropna()
    if data.empty:
        raise AnalysisError("no complete row for the requested model")
    try:
        fit = cox_regression(data, time, event, covariates, alpha=alpha)
    except Exception as exc:
        raise AnalysisError(f"the Cox model could not be fitted: {exc}") from exc

    table_frame = _order_terms(fit.table, covariates)
    rows = [
        {
            "label": str(row["term"]),
            "kind": "cox",
            "cells": {
                "term": str(row["term"]),
                "hr": f"{row['hr']:.3f}",
                "ci": _ci_text(
                    CI(lower=row["ci_low"], upper=row["ci_high"], method="Wald")
                ),
                "p": _fmt_p(float(row["p"])),
            },
        }
        for _, row in table_frame.iterrows()
    ]
    columns = [
        {"key": "term", "label": "Term"},
        {"key": "hr", "label": "Hazard ratio"},
        {"key": "ci", "label": "95% CI"},
        {"key": "p", "label": "p"},
    ]
    notes = [
        f"Efron ties; {fit.events} event(s) in {fit.n} rows. A hazard ratio above 1 means a "
        "higher hazard (faster event) per unit of the term.",
        "Categorical covariates are one-hot coded with their first sorted level as the reference.",
    ]
    if fit.concordance is not None:
        notes.append(f"Concordance index: {fit.concordance:.3f}.")
    if fit.ph_test is not None:
        bad = fit.ph_test[fit.ph_test["p"] < 0.05]
        notes.append(
            "Proportional-hazards check (Grambsch-Therneau): "
            + (
                "violated for "
                + ", ".join(bad["term"])
                + " — interpret those hazard ratios with care."
                if len(bad)
                else "no term shows a violation at p < 0.05."
            )
        )
    else:
        notes.append(
            "The proportional-hazards check and the concordance index need the optional "
            "'survival' extra (lifelines) and were not computed."
        )
    notes.extend(fit.warnings)

    values: list[dict[str, Any]] = []
    for _, row in table_frame.iterrows():
        term = str(row["term"])
        values.append(
            {
                "name": f"cox:{term}:hr",
                "label": f"Hazard ratio, {term}",
                "value": float(row["hr"]),
                "ci_low": float(row["ci_low"]),
                "ci_high": float(row["ci_high"]),
                "n": fit.n,
            }
        )
        values.append(
            {
                "name": f"cox:{term}:p",
                "label": f"p-value, {term}",
                "value": float(row["p"]),
                "p_value": float(row["p"]),
                "n": fit.n,
            }
        )
    return AnalysisOutcome(
        method="cox",
        n=int(fit.n),
        result={
            "time": time,
            "event": event,
            "covariates": covariates,
            "terms": [
                {
                    "term": str(row["term"]),
                    "hr": float(row["hr"]),
                    "ci_low": float(row["ci_low"]),
                    "ci_high": float(row["ci_high"]),
                    "z": float(row["z"]),
                    "p": float(row["p"]),
                }
                for _, row in table_frame.iterrows()
            ],
            "n": int(fit.n),
            "events": int(fit.events),
            "ties": fit.ties,
            "concordance": fit.concordance,
            "ph_test": None
            if fit.ph_test is None
            else fit.ph_test.to_dict(orient="records"),
            "warnings": fit.warnings,
            "references": fit.references,
        },
        table={"columns": columns, "rows": rows, "notes": notes},
        values=values,
    )


def _empirical_youden(y: np.ndarray, scores: np.ndarray) -> tuple[float, float, float]:
    """The cut-off maximising sensitivity + specificity - 1, computed on the sample.

    This is the empirical optimum, so it is optimistic by construction: it is reported
    as a description of this cohort, never as a validated threshold.
    """
    order = np.argsort(-scores, kind="mergesort")
    labels, sorted_scores = y[order], scores[order]
    # Ties must move together, or a cut-off would split identical values.
    keep = np.r_[np.diff(sorted_scores) != 0, True]
    tp = np.cumsum(labels)[keep]
    fp = np.cumsum(1 - labels)[keep]
    thresholds = sorted_scores[keep]
    positives, negatives = labels.sum(), (1 - labels).sum()
    if positives == 0 or negatives == 0:
        raise AnalysisError("both outcome classes are required to choose a cut-off")
    sensitivity = tp / positives
    specificity = 1 - fp / negatives
    best = int(np.argmax(sensitivity + specificity))
    return float(thresholds[best]), float(sensitivity[best]), float(specificity[best])


def diagnostic(
    frame: pd.DataFrame,
    *,
    test: str,
    outcome: str,
    cutoff: float | None = None,
    pos_label: str | None = None,
    alpha: float = 0.05,
) -> AnalysisOutcome:
    """ROC AUC, and sensitivity/specificity/predictive values at a cut-off."""
    if not test or not outcome:
        raise AnalysisError(
            "a diagnostic analysis needs a test column and an outcome column"
        )
    missing = [column for column in (test, outcome) if column not in frame.columns]
    if missing:
        raise AnalysisError("not in this version: " + ", ".join(missing))
    if test == outcome:
        raise AnalysisError("the test and the outcome must be two different columns")
    scores = _numeric(frame, test)
    labels = frame[outcome]
    data = pd.DataFrame({test: scores, outcome: labels}).dropna()
    if data.empty:
        raise AnalysisError("no row has both a test value and an outcome")
    levels = [str(value) for value in pd.unique(data[outcome])]
    if len(levels) != 2:
        raise AnalysisError(
            f"the outcome column '{outcome}' must have exactly two levels; it has {len(levels)}"
        )
    try:
        auc_info = delong_auc(
            list(data[outcome]),
            list(data[test]),
            pos_label=pos_label,
            alpha=alpha,
        )
    except Exception as exc:
        raise AnalysisError(f"the AUC could not be computed: {exc}") from exc

    used_label = auc_info["pos_label"]
    if cutoff is None:
        binary = np.array(
            [1.0 if str(value) == str(used_label) else 0.0 for value in data[outcome]]
        )
        chosen, _, _ = _empirical_youden(binary, data[test].to_numpy(dtype=float))
        cutoff = chosen
        cutoff_note = (
            f"No cut-off was given, so the one maximising Youden's J in this sample was used "
            f"({cutoff:.4g}). It is optimistic: a threshold chosen on the same data overstates "
            "accuracy, and must be validated out of sample."
        )
    else:
        cutoff_note = f"The cut-off was fixed at {cutoff:.4g}; scores at or above it are called positive."

    tp, fp, fn, tn = confusion_at(
        list(data[outcome]), list(data[test]), cutoff, pos_label=used_label
    )
    try:
        accuracy = diagnostic_accuracy(tp, fp, fn, tn, alpha=alpha)
    except Exception as exc:
        raise AnalysisError(
            f"the accuracy measures could not be computed: {exc}"
        ) from exc

    table = {
        "columns": [
            {"key": "measure", "label": "Measure"},
            {"key": "value", "label": "Estimate"},
            {"key": "ci", "label": "95% CI"},
        ],
        "rows": [
            {
                "label": "AUC",
                "cells": {
                    "measure": "AUC (DeLong)",
                    "value": f"{auc_info['auc']:.3f}",
                    "ci": _ci_text(auc_info["ci"]),
                },
            },
            {
                "label": "Sensitivity",
                "cells": {
                    "measure": "Sensitivity",
                    "value": f"{accuracy.sensitivity:.3f}",
                    "ci": _ci_text(accuracy.sensitivity_ci),
                },
            },
            {
                "label": "Specificity",
                "cells": {
                    "measure": "Specificity",
                    "value": f"{accuracy.specificity:.3f}",
                    "ci": _ci_text(accuracy.specificity_ci),
                },
            },
            {
                "label": "PPV",
                "cells": {
                    "measure": "Positive predictive value",
                    "value": f"{accuracy.ppv:.3f}",
                    "ci": _ci_text(accuracy.ppv_ci),
                },
            },
            {
                "label": "NPV",
                "cells": {
                    "measure": "Negative predictive value",
                    "value": f"{accuracy.npv:.3f}",
                    "ci": _ci_text(accuracy.npv_ci),
                },
            },
            {
                "label": "LR+",
                "cells": {
                    "measure": "Likelihood ratio, positive",
                    "value": "–"
                    if accuracy.lr_positive is None
                    else f"{accuracy.lr_positive:.2f}",
                    "ci": _ci_text(accuracy.lr_positive_ci),
                },
            },
            {
                "label": "LR-",
                "cells": {
                    "measure": "Likelihood ratio, negative",
                    "value": "–"
                    if accuracy.lr_negative is None
                    else f"{accuracy.lr_negative:.2f}",
                    "ci": _ci_text(accuracy.lr_negative_ci),
                },
            },
            {
                "label": "Youden J",
                "cells": {
                    "measure": "Youden's J",
                    "value": f"{accuracy.youden:.3f}",
                    "ci": "",
                },
            },
        ],
        "notes": [
            cutoff_note,
            f"Positive class: '{used_label}'. Cut-off {cutoff:.4g}; "
            f"tp {tp}, fp {fp}, fn {fn}, tn {tn}.",
            f"Observed prevalence in this population: {accuracy.prevalence_observed:.1%}. PPV and NPV "
            "belong to this prevalence and do not transfer to a population with a different one.",
            *accuracy.warnings,
        ],
    }
    values = [
        {
            "name": f"{test}:auc",
            "label": f"AUC ({test} vs {outcome})",
            "value": float(auc_info["auc"]),
            "ci_low": float(auc_info["ci"].lower),
            "ci_high": float(auc_info["ci"].upper),
            "n": int(auc_info["n_positive"] + auc_info["n_negative"]),
        },
        {
            "name": f"{test}:sensitivity",
            "label": f"Sensitivity ({test})",
            "value": float(accuracy.sensitivity),
            "ci_low": float(accuracy.sensitivity_ci.lower),
            "ci_high": float(accuracy.sensitivity_ci.upper),
            "n": int(auc_info["n_positive"]),
        },
        {
            "name": f"{test}:specificity",
            "label": f"Specificity ({test})",
            "value": float(accuracy.specificity),
            "ci_low": float(accuracy.specificity_ci.lower),
            "ci_high": float(accuracy.specificity_ci.upper),
            "n": int(auc_info["n_negative"]),
        },
    ]
    return AnalysisOutcome(
        method="diagnostic",
        n=len(data),
        result={
            "test": test,
            "outcome": outcome,
            "pos_label": str(used_label),
            "cutoff": float(cutoff),
            "auc": {
                "estimate": float(auc_info["auc"]),
                "ci_low": float(auc_info["ci"].lower),
                "ci_high": float(auc_info["ci"].upper),
                "n_positive": int(auc_info["n_positive"]),
                "n_negative": int(auc_info["n_negative"]),
            },
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "accuracy": {
                "sensitivity": float(accuracy.sensitivity),
                "specificity": float(accuracy.specificity),
                "ppv": float(accuracy.ppv),
                "npv": float(accuracy.npv),
                "lr_positive": accuracy.lr_positive,
                "lr_negative": accuracy.lr_negative,
                "youden": float(accuracy.youden),
            },
            "warnings": accuracy.warnings,
            "references": accuracy.references,
        },
        table=table,
        values=values,
    )


def ratio_2x2(
    frame: pd.DataFrame,
    *,
    exposure: str,
    outcome: str,
    alpha: float = 0.05,
) -> AnalysisOutcome:
    """Odds ratio, risk ratio and risk difference for a 2x2 table."""
    if not exposure or not outcome:
        raise AnalysisError(
            "a 2x2 analysis needs an exposure column and an outcome column"
        )
    missing = [column for column in (exposure, outcome) if column not in frame.columns]
    if missing:
        raise AnalysisError("not in this version: " + ", ".join(missing))
    if exposure == outcome:
        raise AnalysisError(
            "the exposure and the outcome must be two different columns"
        )
    data = frame[[exposure, outcome]].dropna()
    if data.empty:
        raise AnalysisError("no complete row for the exposure and the outcome")
    try:
        table = TwoByTwo.from_crosstab(data, exposure, outcome)
        result = analyze_twobytwo(table, alpha=alpha)
    except ValueError as exc:
        raise AnalysisError(str(exc)) from exc

    def _row(label: str, measure: str, estimate: float, ci: Any) -> dict[str, Any]:
        return {
            "label": label,
            "cells": {
                "measure": measure,
                "value": f"{estimate:.3f}",
                "ci": _ci_text(ci),
            },
        }

    rows = [
        _row("Odds ratio", "Odds ratio", result.odds_ratio, result.odds_ratio_ci),
        _row("Risk ratio", "Risk ratio", result.relative_risk, result.relative_risk_ci),
        _row(
            "Risk difference",
            "Risk difference",
            result.risk_difference,
            result.risk_difference_ci,
        ),
    ]
    notes = [
        f"{result.exposure_name} '{result.exposure_level}' (comparison) against "
        f"'{result.reference_level}' (reference); event = '{result.event_level}'.",
        f"Risk in the exposed: {result.risk_exposed:.3f}; in the reference: {result.risk_reference:.3f}. "
        f"Primary test: {result.primary_test}, p {_p_phrase(result.primary_pvalue)}.",
        "An odds ratio overstates a risk ratio when the outcome is common; the risk ratio is the "
        "measure to report for a cohort design.",
        *result.guidance,
    ]
    if result.haldane_applied:
        notes.append(
            "A cell was zero: the Haldane-Anscombe correction (+0.5) was applied."
        )
    cells = {
        "label": "2x2 counts",
        "cells": {
            "measure": "exposed / reference, event / no event",
            "value": f"{result.a}, {result.b} / {result.c}, {result.d}",
            "ci": "",
        },
    }
    values = [
        {
            "name": f"{exposure}:odds_ratio",
            "label": f"Odds ratio ({outcome} by {exposure})",
            "value": float(result.odds_ratio),
            "ci_low": float(result.odds_ratio_ci.lower),
            "ci_high": float(result.odds_ratio_ci.upper),
            "n": int(result.n_total),
        },
        {
            "name": f"{exposure}:relative_risk",
            "label": f"Risk ratio ({outcome} by {exposure})",
            "value": float(result.relative_risk),
            "ci_low": float(result.relative_risk_ci.lower),
            "ci_high": float(result.relative_risk_ci.upper),
            "n": int(result.n_total),
        },
        {
            "name": f"{exposure}:risk_difference",
            "label": f"Risk difference ({outcome} by {exposure})",
            "value": float(result.risk_difference),
            "ci_low": float(result.risk_difference_ci.lower),
            "ci_high": float(result.risk_difference_ci.upper),
            "n": int(result.n_total),
        },
        {
            "name": f"{exposure}:p",
            "label": f"p-value ({outcome} by {exposure})",
            "value": float(result.primary_pvalue),
            "p_value": float(result.primary_pvalue),
            "n": int(result.n_total),
        },
    ]
    return AnalysisOutcome(
        method="ratio2x2",
        n=int(result.n_total),
        result=result.legacy_dict(),
        table={
            "columns": [
                {"key": "measure", "label": "Measure"},
                {"key": "value", "label": "Estimate"},
                {"key": "ci", "label": "95% CI"},
            ],
            "rows": [*rows, cells],
            "notes": notes,
        },
        values=values,
    )


def logistic(
    frame: pd.DataFrame,
    *,
    outcome: str,
    covariates: list[str],
    event_level: str | None = None,
    alpha: float = 0.05,
) -> AnalysisOutcome:
    """Binary logistic regression: an odds ratio with its interval per term."""
    if not outcome:
        raise AnalysisError("a logistic model needs an outcome column")
    if not covariates:
        raise AnalysisError("a logistic model needs at least one covariate")
    needed = [outcome, *covariates]
    missing = [column for column in needed if column not in frame.columns]
    if missing:
        raise AnalysisError("not in this version: " + ", ".join(missing))
    if outcome in covariates:
        raise AnalysisError("the outcome cannot also be a covariate")
    data = frame[needed].dropna()
    if data.empty:
        raise AnalysisError("no complete row for the requested model")
    outcome_levels = sorted(data[outcome].astype(str).unique())
    if len(outcome_levels) != 2:
        raise AnalysisError(
            f"the outcome column '{outcome}' must have exactly two levels; "
            f"it has {len(outcome_levels)}"
        )
    # The vendor models the higher sorted level unless told otherwise; name that level.
    used_event = str(event_level) if event_level is not None else outcome_levels[1]
    try:
        fit = logistic_regression(
            data, outcome, covariates, event_level=used_event, alpha=alpha
        )
    except Exception as exc:
        raise AnalysisError(f"the logistic model could not be fitted: {exc}") from exc

    table_frame = _order_terms(fit.table, covariates)
    rows = [
        {
            "label": str(row["term"]),
            "kind": "logistic",
            "cells": {
                "term": str(row["term"]),
                "or": f"{row['odds_ratio']:.3f}",
                "ci": _ci_text(
                    CI(lower=row["ci_low"], upper=row["ci_high"], method="Wald")
                ),
                "p": _fmt_p(float(row["p"])),
            },
        }
        for _, row in table_frame.iterrows()
    ]
    notes = [
        f"Odds ratios for the event '{used_event}' ({fit.events} event(s) in {fit.n} rows). "
        "An odds ratio overstates a risk ratio when the outcome is common.",
        "Categorical covariates are one-hot coded with their first sorted level as the reference.",
    ]
    if fit.auc is not None:
        low, high = fit.auc_ci or (float("nan"), float("nan"))
        notes.append(
            f"Discrimination of the fitted model: AUC {fit.auc:.3f} ({low:.3f}–{high:.3f})."
        )
    if fit.pseudo_r2 is not None:
        notes.append(f"McFadden pseudo-R²: {fit.pseudo_r2:.3f}.")
    notes.extend(fit.warnings)

    values: list[dict[str, Any]] = []
    for _, row in table_frame.iterrows():
        term = str(row["term"])
        values.append(
            {
                "name": f"logistic:{term}:or",
                "label": f"Odds ratio, {term}",
                "value": float(row["odds_ratio"]),
                "ci_low": float(row["ci_low"]),
                "ci_high": float(row["ci_high"]),
                "n": fit.n,
            }
        )
        values.append(
            {
                "name": f"logistic:{term}:p",
                "label": f"p-value, {term}",
                "value": float(row["p"]),
                "p_value": float(row["p"]),
                "n": fit.n,
            }
        )
    if fit.auc is not None:
        low, high = fit.auc_ci or (float("nan"), float("nan"))
        values.append(
            {
                "name": "logistic:auc",
                "label": "AUC of the fitted model",
                "value": float(fit.auc),
                "ci_low": None if np.isnan(low) else float(low),
                "ci_high": None if np.isnan(high) else float(high),
                "n": fit.n,
            }
        )
    return AnalysisOutcome(
        method="logistic",
        n=int(fit.n),
        result={
            "outcome": outcome,
            "covariates": covariates,
            "terms": [
                {
                    "term": str(row["term"]),
                    "or": float(row["odds_ratio"]),
                    "ci_low": float(row["ci_low"]),
                    "ci_high": float(row["ci_high"]),
                    "z": float(row["z"]),
                    "p": float(row["p"]),
                }
                for _, row in table_frame.iterrows()
            ],
            "n": int(fit.n),
            "events": fit.events,
            "auc": fit.auc,
            "auc_ci": fit.auc_ci,
            "pseudo_r2": fit.pseudo_r2,
            "warnings": fit.warnings,
            "references": fit.references,
        },
        table={
            "columns": [
                {"key": "term", "label": "Term"},
                {"key": "or", "label": "Odds ratio"},
                {"key": "ci", "label": "95% CI"},
                {"key": "p", "label": "p"},
            ],
            "rows": rows,
            "notes": notes,
        },
        values=values,
    )


def mantel_haenszel(
    frame: pd.DataFrame,
    *,
    exposure: str,
    outcome: str,
    stratum: str,
    alpha: float = 0.05,
) -> AnalysisOutcome:
    """Pooled odds and risk ratios across strata, with the Breslow-Day test of homogeneity."""
    if not (exposure and outcome and stratum):
        raise AnalysisError(
            "a Mantel-Haenszel analysis needs an exposure, an outcome and a stratification column"
        )
    needed = [exposure, outcome, stratum]
    missing = [column for column in needed if column not in frame.columns]
    if missing:
        raise AnalysisError("not in this version: " + ", ".join(missing))
    if len({exposure, outcome, stratum}) != 3:
        raise AnalysisError(
            "exposure, outcome and stratum must be three different columns"
        )
    data = frame[needed].dropna()
    if data.empty:
        raise AnalysisError(
            "no complete row for the exposure, the outcome and the stratum"
        )
    # Orient the table the same way the 2x2 analysis does, or the same two columns
    # would give an odds ratio and its reciprocal in two places of the app.
    exposure_levels = sorted(data[exposure].astype(str).unique())
    outcome_levels = sorted(data[outcome].astype(str).unique())
    reference = detect_reference_level(exposure_levels)
    exposure_level = (
        next(level for level in exposure_levels if level != reference)
        if reference
        else exposure_levels[-1]
    )
    event = detect_event_level(outcome_levels) or outcome_levels[-1]
    try:
        pooled = mantel_haenszel_vendor(
            data,
            exposure,
            outcome,
            stratum,
            exposure_level=exposure_level,
            event_level=event,
            alpha=alpha,
        )
    except ValueError as exc:
        raise AnalysisError(str(exc)) from exc

    rows = [
        {
            "label": "Odds ratio (Mantel-Haenszel)",
            "cells": {
                "measure": "Pooled odds ratio",
                "value": f"{pooled.or_mh:.3f}",
                "ci": _ci_text(pooled.or_mh_ci),
            },
        },
        {
            "label": "Risk ratio (Mantel-Haenszel)",
            "cells": {
                "measure": "Pooled risk ratio",
                "value": f"{pooled.rr_mh:.3f}",
                "ci": _ci_text(pooled.rr_mh_ci),
            },
        },
        {
            "label": "Crude odds ratio",
            "cells": {
                "measure": "Crude odds ratio (strata ignored)",
                "value": f"{pooled.crude_or:.3f}",
                "ci": "",
            },
        },
        {
            "label": "Mantel-Haenszel test",
            "cells": {
                "measure": "Test of no association across strata",
                "value": f"chi-square = {pooled.mh_test_statistic:.3f}",
                "ci": f"p {_p_phrase(pooled.mh_test_p)}",
            },
        },
        {
            "label": "Breslow-Day",
            "cells": {
                "measure": "Test of homogeneous odds ratios",
                "value": f"chi-square = {pooled.breslow_day_statistic:.3f}",
                "ci": f"p {_p_phrase(pooled.breslow_day_p)}",
            },
        },
    ]
    notes = [
        f"'{exposure_level}' is compared with '{reference or exposure_levels[0]}'; the event is "
        f"'{event}'.",
        f"{pooled.n_strata} stratum/strata. The pooled estimate is the stratified association; the "
        "crude one ignores the stratum and is shown for comparison.",
        "If Breslow-Day rejects homogeneity the strata do not share one odds ratio, and the pooled "
        "value hides that: report the per-stratum estimates instead.",
        *pooled.warnings,
    ]
    if abs(pooled.or_mh - pooled.crude_or) > 0.1 * max(abs(pooled.crude_or), 1e-9):
        notes.append(
            "The pooled and crude odds ratios differ by more than 10%: the stratum confounds the "
            "exposure-outcome association."
        )
    values = [
        {
            "name": f"{exposure}:mh_or",
            "label": f"Mantel-Haenszel odds ratio ({outcome} by {exposure}, stratified by {stratum})",
            "value": float(pooled.or_mh),
            "ci_low": float(pooled.or_mh_ci.lower),
            "ci_high": float(pooled.or_mh_ci.upper),
            "n": len(data),
        },
        {
            "name": f"{exposure}:mh_rr",
            "label": f"Mantel-Haenszel risk ratio ({outcome} by {exposure}, stratified by {stratum})",
            "value": float(pooled.rr_mh),
            "ci_low": float(pooled.rr_mh_ci.lower),
            "ci_high": float(pooled.rr_mh_ci.upper),
            "n": len(data),
        },
        {
            "name": f"{exposure}:mh_p",
            "label": f"Mantel-Haenszel p-value ({outcome} by {exposure}, stratified by {stratum})",
            "value": float(pooled.mh_test_p),
            "p_value": float(pooled.mh_test_p),
            "n": len(data),
        },
    ]
    return AnalysisOutcome(
        method="mantel_haenszel",
        n=len(data),
        result={
            "exposure": exposure,
            "outcome": outcome,
            "stratum": stratum,
            "or_mh": float(pooled.or_mh),
            "or_mh_ci": _ci_pair(pooled.or_mh_ci),
            "rr_mh": float(pooled.rr_mh),
            "rr_mh_ci": _ci_pair(pooled.rr_mh_ci),
            "crude_or": float(pooled.crude_or),
            "breslow_day": {
                "statistic": float(pooled.breslow_day_statistic),
                "p_value": float(pooled.breslow_day_p),
            },
            "mh_test": {
                "statistic": float(pooled.mh_test_statistic),
                "p_value": float(pooled.mh_test_p),
            },
            "n_strata": int(pooled.n_strata),
            "per_stratum": pooled.per_stratum.to_dict(orient="records"),
            "warnings": pooled.warnings,
            "references": pooled.references,
        },
        table={
            "columns": [
                {"key": "measure", "label": "Measure"},
                {"key": "value", "label": "Estimate"},
                {"key": "ci", "label": "95% CI"},
            ],
            "rows": rows,
            "notes": notes,
        },
        values=values,
    )


def agreement(
    frame: pd.DataFrame,
    *,
    raters: list[str],
    measure: str = "icc",
    weights: str | None = None,
    icc_model: str = "ICC(2,1)",
    alpha: float = 0.05,
) -> AnalysisOutcome:
    """Agreement between measurements: ICC or Bland-Altman (continuous), Cohen's kappa (categorical)."""
    if measure not in ("icc", "bland_altman", "kappa"):
        raise AnalysisError(
            f"unknown agreement measure {measure!r}; expected icc, bland_altman or kappa"
        )
    if len(raters) < 2:
        raise AnalysisError("agreement needs at least two measurement columns")
    if len(set(raters)) != len(raters):
        raise AnalysisError("the measurement columns must be different")
    missing = [column for column in raters if column not in frame.columns]
    if missing:
        raise AnalysisError("not in this version: " + ", ".join(missing))

    if measure == "kappa":
        if len(raters) != 2:
            raise AnalysisError("Cohen's kappa compares exactly two raters")
        data = frame[raters].dropna().astype(str)
        if data.empty:
            raise AnalysisError("no row has both ratings")
        table = pd.crosstab(data[raters[0]], data[raters[1]])
        if table.shape[0] != table.shape[1]:
            raise AnalysisError(
                "kappa needs the same categories on both sides; a category present in one rater only "
                "cannot be compared"
            )
        try:
            result = cohens_kappa(table.to_numpy(), weights=weights, alpha=alpha)
        except Exception as exc:
            raise AnalysisError(f"kappa could not be computed: {exc}") from exc
        rows = [
            {
                "label": "Cohen's kappa",
                "cells": {
                    "measure": "Kappa",
                    "value": f"{result.kappa:.3f}",
                    "ci": _ci_text(result.ci),
                },
            },
            {
                "label": "Observed agreement",
                "cells": {
                    "measure": "Observed agreement",
                    "value": f"{result.observed_agreement:.3f}",
                    "ci": "",
                },
            },
            {
                "label": "Expected agreement",
                "cells": {
                    "measure": "Agreement expected by chance",
                    "value": f"{result.expected_agreement:.3f}",
                    "ci": "",
                },
            },
        ]
        notes = [
            f"{result.interpretation}; {result.n} paired rating(s)"
            + (", weighted" if result.weighted else ", unweighted")
            + ".",
            "Cohen's kappa assumes two raters and no ordering; for more raters use Fleiss' kappa, "
            "which this module does not implement.",
            *result.references,
        ]
        return AnalysisOutcome(
            method="agreement",
            n=int(result.n),
            result={
                "measure": "kappa",
                "raters": raters,
                "kappa": float(result.kappa),
                "ci": _ci_pair(result.ci),
                "observed_agreement": float(result.observed_agreement),
                "expected_agreement": float(result.expected_agreement),
                "interpretation": result.interpretation,
            },
            table={
                "columns": [
                    {"key": "measure", "label": "Measure"},
                    {"key": "value", "label": "Estimate"},
                    {"key": "ci", "label": "95% CI"},
                ],
                "rows": rows,
                "notes": notes,
            },
            values=[
                {
                    "name": "agreement:kappa",
                    "label": f"Cohen's kappa ({raters[0]} vs {raters[1]})",
                    "value": float(result.kappa),
                    "ci_low": float(result.ci.lower),
                    "ci_high": float(result.ci.upper),
                    "n": int(result.n),
                }
            ],
        )

    numeric = []
    for column in raters:
        series = frame[column]
        if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(
            series
        ):
            raise AnalysisError(f"column '{column}' is not numeric ({series.dtype})")
        numeric.append(column)
    wide = frame[numeric].dropna()
    if wide.empty:
        raise AnalysisError("no row has every measurement")

    if measure == "bland_altman":
        if len(raters) != 2:
            raise AnalysisError("Bland-Altman compares exactly two measurements")
        try:
            result = bland_altman(
                wide[raters[0]].to_numpy(), wide[raters[1]].to_numpy(), alpha=alpha
            )
        except Exception as exc:
            raise AnalysisError(f"the Bland-Altman analysis failed: {exc}") from exc
        rows = [
            {
                "label": "Bias",
                "cells": {
                    "measure": f"Mean difference ({raters[0]} - {raters[1]})",
                    "value": f"{result.bias:.3f}",
                    "ci": _ci_text(result.bias_ci),
                },
            },
            {
                "label": "Limits of agreement",
                "cells": {
                    "measure": "Lower limit",
                    "value": f"{result.loa_lower:.3f}",
                    "ci": _ci_text(result.loa_lower_ci),
                },
            },
            {
                "label": "",
                "cells": {
                    "measure": "Upper limit",
                    "value": f"{result.loa_upper:.3f}",
                    "ci": _ci_text(result.loa_upper_ci),
                },
            },
            {
                "label": "Within limits",
                "cells": {
                    "measure": "Share of pairs inside the limits",
                    "value": f"{result.within_loa_pct:.1f}%",
                    "ci": "",
                },
            },
            {
                "label": "Proportional bias",
                "cells": {
                    "measure": "Slope of the difference on the mean",
                    "value": f"{result.proportional_bias_slope:.4f}",
                    "ci": f"p {_p_phrase(result.proportional_bias_p)}",
                },
            },
        ]
        notes = [
            f"Differences are {raters[0]} - {raters[1]}; {result.n} complete pair(s).",
            "A slope significantly different from zero means the disagreement depends on the "
            "magnitude, and the constant limits of agreement then do not describe it well.",
            *result.warnings,
        ]
        return AnalysisOutcome(
            method="agreement",
            n=int(result.n),
            result={
                "measure": "bland_altman",
                "raters": raters,
                "bias": float(result.bias),
                "bias_ci": _ci_pair(result.bias_ci),
                "loa": [float(result.loa_lower), float(result.loa_upper)],
                "within_loa_pct": float(result.within_loa_pct),
                "proportional_bias_slope": float(result.proportional_bias_slope),
                "proportional_bias_p": float(result.proportional_bias_p),
                "warnings": result.warnings,
                "references": result.references,
            },
            table={
                "columns": [
                    {"key": "measure", "label": "Measure"},
                    {"key": "value", "label": "Estimate"},
                    {"key": "ci", "label": "95% CI"},
                ],
                "rows": rows,
                "notes": notes,
            },
            values=[
                {
                    "name": "agreement:bias",
                    "label": f"Bias ({raters[0]} - {raters[1]})",
                    "value": float(result.bias),
                    "ci_low": float(result.bias_ci.lower),
                    "ci_high": float(result.bias_ci.upper),
                    "n": int(result.n),
                },
                {
                    "name": "agreement:loa_lower",
                    "label": "Lower limit of agreement",
                    "value": float(result.loa_lower),
                    "n": int(result.n),
                },
                {
                    "name": "agreement:loa_upper",
                    "label": "Upper limit of agreement",
                    "value": float(result.loa_upper),
                    "n": int(result.n),
                },
            ],
        )

    try:
        result = icc(wide, model=icc_model, alpha=alpha)
    except Exception as exc:
        raise AnalysisError(f"the ICC could not be computed: {exc}") from exc
    rows = [
        {
            "label": "ICC",
            "cells": {
                "measure": result.model,
                "value": f"{result.icc:.3f}",
                "ci": _ci_text(result.ci),
            },
        },
        {
            "label": "F test",
            "cells": {
                "measure": f"F({result.df1:.0f}, {result.df2:.0f}) = {result.f_statistic:.3f}",
                "value": _fmt_p(result.p_value),
                "ci": "",
            },
        },
    ]
    notes = [
        f"{result.n_subjects} subject(s) x {result.n_raters} measurement(s), complete cases only.",
        f"{result.interpretation} reliability (Koo & Li). {result.model}: "
        + (
            "two-way random effects, absolute agreement."
            if result.model == "ICC(2,1)"
            else "two-way mixed effects, consistency."
        ),
        *result.references,
    ]
    return AnalysisOutcome(
        method="agreement",
        n=int(result.n_subjects),
        result={
            "measure": "icc",
            "raters": raters,
            "model": icc_model,
            "model_label": result.model,
            "icc": float(result.icc),
            "ci": _ci_pair(result.ci),
            "f": {
                "statistic": float(result.f_statistic),
                "df1": float(result.df1),
                "df2": float(result.df2),
                "p_value": float(result.p_value),
            },
            "interpretation": result.interpretation,
            "n_subjects": int(result.n_subjects),
            "n_raters": int(result.n_raters),
            "references": result.references,
        },
        table={
            "columns": [
                {"key": "measure", "label": "Measure"},
                {"key": "value", "label": "Estimate"},
                {"key": "ci", "label": "95% CI"},
            ],
            "rows": rows,
            "notes": notes,
        },
        values=[
            {
                "name": "agreement:icc",
                "label": f"{result.model} ({', '.join(raters)})",
                "value": float(result.icc),
                "ci_low": float(result.ci.lower),
                "ci_high": float(result.ci.upper),
                "n": int(result.n_subjects),
            }
        ],
    )


def mcar(
    frame: pd.DataFrame,
    *,
    variables: list[str] | None = None,
    alpha: float = 0.05,
) -> AnalysisOutcome:
    """Little's MCAR test plus the missingness pattern of each variable.

    MCAR is the assumption no imputation can rescue: under it, complete cases are
    unbiased (merely wasteful). Rejecting it says the mechanism is MAR or MNAR, which is
    what justifies multiple imputation and what the methods paragraph has to state.
    """
    columns = [
        column
        for column in (variables or list(frame.columns))
        if column in frame.columns
    ]
    if not columns:
        raise AnalysisError("no column to test")
    numeric = [
        column
        for column in columns
        if pd.api.types.is_numeric_dtype(frame[column])
        and not pd.api.types.is_bool_dtype(frame[column])
    ]
    if len(numeric) < 2:
        raise AnalysisError(
            "Little's test needs at least two numeric columns with data; "
            f"the selected variables have {len(numeric)}"
        )
    try:
        test = littles_mcar_test(frame[numeric])
    except Exception as exc:
        raise AnalysisError(f"Little's test could not be computed: {exc}") from exc
    if "error" in test:
        raise AnalysisError(str(test["error"]))

    summary = missingness_summary(frame, columns)
    missing_rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        missing_rows.append(
            {
                "label": str(row["column"]),
                "cells": {
                    "column": f"{row['column']} ({row['kind']})",
                    "missing": str(int(row["missing"])),
                    "share": f"{float(row['share']):.1%}",
                },
            }
        )
    rows = [
        {
            "label": "Little's MCAR test",
            "cells": {
                "column": f"chi-square = {test['statistic']:.3f}, df = {test['df']}",
                "missing": f"{test['n_patterns']} pattern(s)",
                "share": f"p {_p_phrase(test['p_value'])}",
            },
        },
        *missing_rows,
    ]
    notes = [
        test["result"] + ": " + test.get("interpretation", ""),
        "The test reads the numeric variables only; a categorical variable's missingness does not "
        "enter the statistic.",
        "MCAR is a property of the mechanism, not of the test: failing to reject it does not prove "
        "the data are MCAR, it means the data are consistent with it.",
        "Under MAR, multiple imputation is valid and complete-case analysis is not; under MNAR "
        "neither removes the bias, and a sensitivity analysis is needed.",
    ]
    return AnalysisOutcome(
        method="mcar",
        n=int(test["n"]),
        result={
            "statistic": float(test["statistic"]),
            "df": int(test["df"]),
            "p_value": float(test["p_value"]),
            "n_patterns": int(test["n_patterns"]),
            "n": int(test["n"]),
            "variables": numeric,
            "evidence_against_mcar": bool(test["p_value"] < alpha),
            "em_iterations": int(test.get("em_iterations") or 0),
            "references": [METHOD_REFERENCES.get("little1988", "Little RJA (1988)")],
        },
        table={
            "columns": [
                {"key": "column", "label": "Variable / statistic"},
                {"key": "missing", "label": "Missing"},
                {"key": "share", "label": "Share / p"},
            ],
            "rows": rows,
            "notes": notes,
        },
        values=[
            {
                "name": "mcar:p",
                "label": "Little's MCAR test p-value",
                "value": float(test["p_value"]),
                "p_value": float(test["p_value"]),
                "n": int(test["n"]),
            }
        ],
    )


def multiple_imputation(
    frame: pd.DataFrame,
    *,
    target: str,
    variables: list[str] | None = None,
    outcome: str | None = None,
    group: str | None = None,
    covariates: list[str] | None = None,
    time: str | None = None,
    event: str | None = None,
    kind: str = "welch",
    m: int = 20,
    maxit: int = 10,
    seed: int | None = None,
    alpha: float = 0.05,
) -> AnalysisOutcome:
    """Impute ``m`` times by chained equations and pool one analysis with Rubin's rules.

    The complete-case analysis is reported next to the pooled one, because the point of
    multiple imputation is the difference between them: if the two agree, the missing
    data were not driving the result.
    """
    if target not in ("compare", "logistic", "cox"):
        raise AnalysisError(
            f"unknown pooling target {target!r}; expected compare, logistic or cox"
        )
    if m < 2:
        raise AnalysisError(
            "multiple imputation needs at least two imputations to pool"
        )

    needed: list[str] = []
    if target == "compare":
        if not outcome or not group:
            raise AnalysisError(
                "a pooled comparison needs an outcome and a group column"
            )
        # Pooling needs an estimate with a standard error. A mean difference has one; an
        # omnibus Welch ANOVA over three or more groups does not.
        observed = sorted({str(value) for value in frame[group].dropna().unique()})
        if len(observed) != 2:
            raise AnalysisError(
                f"a pooled comparison needs a two-group column; '{group}' has {len(observed)} "
                "levels. Pool one contrast at a time."
            )
        needed = [outcome, group]
    elif target == "logistic":
        if not outcome or not covariates:
            raise AnalysisError(
                "a pooled logistic model needs an outcome and covariates"
            )
        needed = [outcome, *covariates]
    else:
        if not time or not event or not covariates:
            raise AnalysisError(
                "a pooled Cox model needs a time, an event and covariates"
            )
        needed = [time, event, *covariates]
    missing = [column for column in needed if column not in frame.columns]
    if missing:
        raise AnalysisError("not in this version: " + ", ".join(missing))

    # The imputation model is everything the target reads, plus any extra the user names.
    model_columns = list(dict.fromkeys([*needed, *(variables or [])]))
    incomplete = [column for column in model_columns if frame[column].isna().any()]
    if not incomplete:
        raise AnalysisError(
            "none of the model's columns has a missing value: there is nothing to impute. "
            "Use the ordinary analysis instead."
        )
    data = frame[model_columns].dropna(how="all")
    if len(data) < 20:
        raise AnalysisError("too few complete rows to fit an imputation model")

    spec = ImputationSpec(
        columns=model_columns,
        m=int(m),
        maxit=int(maxit),
        **({"seed": int(seed)} if seed is not None else {}),
    )
    try:
        run = impute(data, spec)
    except Exception as exc:
        raise AnalysisError(f"the imputation failed: {exc}") from exc

    levels = run.mi.levels(model_columns)
    try:
        if target == "compare":
            analysis = lambda d: compare_groups(  # noqa: E731 - a one-line analysis callable
                groups_from_frame(d, group, outcome, levels=levels.get(group)),
                kind=kind,
                alpha=alpha,
            )
        elif target == "logistic":
            analysis = lambda d: logistic_regression(  # noqa: E731
                d, outcome, covariates, levels=levels, alpha=alpha
            )
        else:
            analysis = lambda d: cox_regression(  # noqa: E731
                d,
                time,
                event,
                covariates,
                levels=levels,
                alpha=alpha,
                diagnostics=False,
            )
        pooled = analyze_mi(analysis, run.mi, alpha=alpha)
    except Exception as exc:
        raise AnalysisError(
            f"the analysis could not be pooled over the imputations: {exc}"
        ) from exc

    pooled_frame = pooled.to_frame()
    if pooled_frame.empty:
        raise AnalysisError("the pooled analysis produced no estimable term")

    # The complete-case fit, when the adapter kept one, so the two can sit side by side:
    # the interesting number is the difference between them.
    complete_by_term: dict[str, dict[str, Any]] = {}
    complete_single: dict[str, Any] | None = None
    complete = pooled.complete_case
    if complete is not None:
        complete_table = getattr(complete, "table", None)
        if complete_table is not None and len(complete_table):
            for _, row in complete_table.iterrows():
                complete_by_term[str(row["term"])] = {
                    "estimate": float(
                        row.get("ratio", row.get("hr", row.get("coef", 0.0)))
                    ),
                    "p": float(row.get("p", float("nan"))),
                }
        elif getattr(complete, "estimate", None) is not None:
            ci = getattr(complete, "estimate_ci", None)
            complete_single = {
                "label": f"{(complete.estimate_label or 'estimate').strip()} (complete cases)",
                "cells": {
                    "term": f"{(complete.estimate_label or 'estimate').strip()} (complete cases)",
                    "estimate": f"{float(complete.estimate):.3f}",
                    "ci": "" if ci is None else f"{ci.lower:.3f}–{ci.upper:.3f}",
                    "p": _fmt_p(complete.p_value),
                    "fmi": "",
                    "cc_estimate": "",
                    "cc_p": "",
                },
            }

    rows: list[dict[str, Any]] = []
    values: list[dict[str, Any]] = []
    for _, row in pooled_frame.iterrows():
        term = str(row["term"])
        natural = row.get("natural_estimate")
        natural_low, natural_high = (
            row.get("natural_ci_low"),
            row.get("natural_ci_high"),
        )
        # Ratios are pooled on the log scale; the natural scale is what a reader wants.
        estimate = (
            float(natural)
            if natural is not None and not pd.isna(natural)
            else float(row["estimate"])
        )
        low = (
            natural_low
            if natural_low is not None and not pd.isna(natural_low)
            else row["ci_low"]
        )
        high = (
            natural_high
            if natural_high is not None and not pd.isna(natural_high)
            else row["ci_high"]
        )
        counterpart = complete_by_term.get(term)
        rows.append(
            {
                "label": "(Intercept)" if term == "const" else term,
                "kind": "pooled",
                "cells": {
                    "term": "(Intercept)" if term == "const" else term,
                    "estimate": f"{estimate:.3f}",
                    "ci": f"{float(low):.3f}–{float(high):.3f}",
                    "p": _fmt_p(float(row["p_value"])),
                    "fmi": f"{float(row['fmi']):.2f}",
                    "cc_estimate": ""
                    if counterpart is None
                    else f"{counterpart['estimate']:.3f}",
                    "cc_p": "" if counterpart is None else _fmt_p(counterpart["p"]),
                },
            }
        )
        # An intercept is part of the model but never an effect to report in a manuscript.
        if term == "const":
            continue
        values.append(
            {
                "name": f"mi:{term}",
                "label": f"Pooled estimate, {term}",
                "value": float(estimate),
                "ci_low": float(low),
                "ci_high": float(high),
                "p_value": float(row["p_value"]),
                "n": len(data),
            }
        )
    if complete_single is not None:
        rows.append(
            {
                "label": complete_single["label"],
                "kind": "complete-case",
                "cells": complete_single["cells"],
            }
        )

    has_complete = bool(complete_by_term) or complete_single is not None
    columns = [
        {"key": "term", "label": "Term"},
        {"key": "estimate", "label": "Pooled"},
        {"key": "ci", "label": "95% CI"},
        {"key": "p", "label": "p"},
        {"key": "fmi", "label": "FMI"},
    ]
    if has_complete:
        columns += [
            {"key": "cc_estimate", "label": "Complete case"},
            {"key": "cc_p", "label": "p (complete case)"},
        ]

    notes = [
        f"{pooled.m} imputations pooled with Rubin's rules (Barnard-Rubin df); the imputation "
        f"model had {len(model_columns)} column(s): {', '.join(model_columns)}.",
        "The fraction of missing information (FMI) is the share of the estimate's variance that "
        "comes from the missing data: a large FMI means m matters, and more imputations are needed.",
    ]
    if has_complete:
        notes.append(
            "The complete-case estimate is shown next to the pooled one. Where the two agree, the "
            "missing data were not driving the result; where they disagree, the complete cases were "
            "not a random subset and the pooled estimate is the one to report."
        )
    for name, rhat in (run.rhat or {}).items():
        if rhat is not None and rhat > 1.05:
            notes.append(
                f"The chains for '{name}' have not mixed (R-hat {rhat:.3f}): raise the number of "
                "iterations before trusting this pooling."
            )
    notes.extend(run.warnings)
    notes.extend(pooled.notes)

    return AnalysisOutcome(
        method="multiple_imputation",
        n=len(data),
        result={
            "target": target,
            "m": int(pooled.m),
            "m_total": int(pooled.m_total),
            "model_columns": model_columns,
            "imputed": run.mi.n_imputed(),
            "methods": dict(run.methods),
            "rhat": {
                k: (None if v is None else float(v))
                for k, v in (run.rhat or {}).items()
            },
            "seed": int(seed) if seed is not None else None,
            "maxit": int(maxit),
            "partial": bool(pooled.partial),
            "terms": pooled_frame.to_dict(orient="records"),
            "tests": {
                name: {
                    "statistic": float(test.statistic),
                    "df": float(test.df2),
                    "p_value": float(test.p_value),
                }
                for name, test in (pooled.tests or {}).items()
            },
            "warnings": [*run.warnings, *pooled.warnings],
            "references": [
                METHOD_REFERENCES.get(
                    "vanbuuren2011",
                    "van Buuren S, Groothuis-Oudshoorn K (2011). mice: multivariate imputation "
                    "by chained equations in R. J Stat Softw 45(3):1-67.",
                )
            ],
        },
        table={"columns": columns, "rows": rows, "notes": notes},
        values=values,
    )
