"""Data-quality scorecard for a cohort version.

Five dimensions (completeness, uniqueness, consistency, uniformity, validity) plus
the study's own clinical rules. The score informs; it never blocks. A dataset that
fails a dimension is still analysable — the point is that the researcher knows which
dimension, and can say so in the methods section.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .vendor.core.criteria import CriterionError, criterion_mask
from .vendor.core.population import EXCLUSION, catalogue

__all__ = ["QualityReport", "audit"]

# Weights sum to 1. Completeness outweighs the rest because a missing value is the
# one defect that changes N; the others change the value, not the count.
_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("completeness", 0.30),
    ("uniqueness", 0.15),
    ("consistency", 0.20),
    ("uniformity", 0.15),
    ("validity", 0.20),
)

_BANDS = ((0.95, "excellent"), (0.85, "good"), (0.70, "fair"), (0.0, "poor"))
_IQR_MULTIPLIER = 1.5
_Z_LIMIT = 4.0


@dataclass
class QualityReport:
    """The scorecard, ready to serialise."""

    rows: int
    columns: int
    score: float
    band: str
    dimensions: list[dict[str, Any]] = field(default_factory=list)
    missing: list[dict[str, Any]] = field(default_factory=list)
    duplicates: dict[str, Any] = field(default_factory=dict)
    inconsistent: list[dict[str, Any]] = field(default_factory=list)
    non_uniform: list[dict[str, Any]] = field(default_factory=list)
    outliers: list[dict[str, Any]] = field(default_factory=list)
    clinical_rules: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def headline(self) -> str:
        return f"{self.score:.0%} ({self.band})"


def _band(score: float) -> str:
    for threshold, label in _BANDS:
        if score >= threshold:
            return label
    return "poor"


def _text_columns(frame: pd.DataFrame) -> list[str]:
    out: list[str] = []
    for name in frame.columns:
        series = frame[name]
        if pd.api.types.is_bool_dtype(series) or pd.api.types.is_numeric_dtype(series):
            continue
        if pd.api.types.is_datetime64_any_dtype(series):
            continue
        out.append(str(name))
    return out


def _completeness(frame: pd.DataFrame) -> tuple[float, list[dict[str, Any]]]:
    total = int(frame.shape[0] * frame.shape[1])
    if total == 0:
        return 1.0, []
    missing_rows: list[dict[str, Any]] = []
    for name in frame.columns:
        n_missing = int(frame[name].isna().sum())
        if n_missing:
            missing_rows.append(
                {
                    "column": str(name),
                    "missing": n_missing,
                    "share": round(n_missing / len(frame), 4),
                }
            )
    missing_rows.sort(key=lambda item: item["missing"], reverse=True)
    filled = total - sum(item["missing"] for item in missing_rows)
    return filled / total, missing_rows


def _uniqueness(frame: pd.DataFrame) -> tuple[float, dict[str, Any]]:
    if frame.empty:
        return 1.0, {"rows": 0, "share": 0.0}
    duplicated = int(frame.duplicated().sum())
    return 1.0 - duplicated / len(frame), {
        "rows": duplicated,
        "share": round(duplicated / len(frame), 4),
    }


def _consistency(
    frame: pd.DataFrame,
) -> tuple[float, list[dict[str, Any]], list[str]]:
    """Text columns that hold something other than text: whitespace, blanks, numbers."""
    issues: list[dict[str, Any]] = []
    warnings: list[str] = []
    text_columns = _text_columns(frame)
    if not text_columns or frame.empty:
        return 1.0, issues, warnings

    offending_rows = 0
    for name in text_columns:
        series = frame[name].dropna()
        if series.empty:
            continue
        text = series.astype(str)
        stripped = text.str.strip()
        padded = int((text != stripped).sum())
        blank = int((stripped == "").sum())
        numeric_like = int(
            pd.to_numeric(
                stripped.str.replace(",", ".", regex=False).str.replace(
                    " ", "", regex=False
                ),
                errors="coerce",
            )
            .notna()
            .sum()
        )
        column_issues: list[str] = []
        if padded:
            column_issues.append("surrounding whitespace")
        if blank:
            column_issues.append("empty strings instead of missing values")
        # A column that is mostly numeric but was read as text is a typing problem
        # the analysis will trip over (its mean is a string sort).
        if numeric_like and numeric_like / len(series) >= 0.5:
            column_issues.append(
                f"{numeric_like} of {len(series)} values look numeric but the column was read as text"
            )
        if column_issues:
            issues.append(
                {
                    "column": name,
                    "issues": column_issues,
                    "rows": max(padded, blank, numeric_like),
                }
            )
            offending_rows += max(padded, blank, numeric_like)
            if any("read as text" in item for item in column_issues):
                warnings.append(
                    f"column '{name}' looks numeric but was read as text; "
                    "statistics on it will not be meaningful"
                )
    share = min(1.0, offending_rows / max(len(frame) * len(text_columns), 1))
    return 1.0 - share, issues, warnings


def _uniformity(frame: pd.DataFrame) -> tuple[float, list[dict[str, Any]]]:
    """The same category written two ways ('Male' / 'male' / 'MALE')."""
    issues: list[dict[str, Any]] = []
    text_columns = _text_columns(frame)
    if not text_columns or frame.empty:
        return 1.0, issues

    involved = 0
    for name in text_columns:
        series = frame[name].dropna()
        if series.empty:
            continue
        text = series.astype(str).str.strip()
        folded = text.str.casefold()
        # Group the case-folded tokens, then count how many distinct spellings each
        # one has: more than one means the same category was written two ways.
        variants = text.groupby(folded).nunique()
        mixed = variants[variants > 1]
        if mixed.empty:
            continue
        affected = int(folded.isin(mixed.index).sum())
        involved += affected
        issues.append(
            {
                "column": name,
                "rows": affected,
                "variants": len(mixed),
                "example": " / ".join(
                    sorted(text[folded == mixed.index[0]].unique())[:3]
                ),
            }
        )
    share = min(1.0, involved / max(len(frame) * len(text_columns), 1))
    return 1.0 - share, issues


def _validity(frame: pd.DataFrame) -> tuple[float, list[dict[str, Any]]]:
    """Rows with a value outside the IQR fences of its column (z-scores are reported too)."""
    numeric = [
        name
        for name in frame.columns
        if pd.api.types.is_numeric_dtype(frame[name])
        and not pd.api.types.is_bool_dtype(frame[name])
    ]
    if not numeric or frame.empty:
        return 1.0, []
    flagged = np.zeros(len(frame), dtype=bool)
    issues: list[dict[str, Any]] = []
    for name in numeric:
        series = frame[name].astype(float)
        observed = series.dropna()
        if len(observed) < 8:
            continue
        q1, q3 = observed.quantile(0.25), observed.quantile(0.75)
        spread = q3 - q1
        if spread <= 0:
            continue
        low, high = q1 - _IQR_MULTIPLIER * spread, q3 + _IQR_MULTIPLIER * spread
        outside = series.notna() & ((series < low) | (series > high))
        sd = observed.std(ddof=1)
        extreme = (
            series.notna()
            & (sd > 0)
            & ((series - observed.mean()).abs() > _Z_LIMIT * sd)
        )
        n_outside = int(outside.sum())
        if not n_outside:
            continue
        flagged |= outside.to_numpy()
        issues.append(
            {
                "column": str(name),
                "rows": n_outside,
                "share": round(n_outside / len(frame), 4),
                "iqr_bounds": [round(float(low), 4), round(float(high), 4)],
                "beyond_z": int(extreme.sum()),
            }
        )
    issues.sort(key=lambda item: item["rows"], reverse=True)
    return 1.0 - float(flagged.mean()), issues


def _clinical_rules(
    frame: pd.DataFrame, config: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], list[str]]:
    """How many rows the study's own anomaly/inclusion rules fire on (not scored)."""
    rules: list[dict[str, Any]] = []
    warnings: list[str] = []
    for criterion in catalogue(config):
        try:
            fires = criterion_mask(frame, criterion.name, criterion.definition)
        except CriterionError as exc:
            warnings.append(
                f"clinical rule '{criterion.name}' cannot be evaluated: {exc}"
            )
            continue
        rules.append(
            {
                "id": criterion.id,
                "family": criterion.family,
                "name": criterion.name,
                "kind": criterion.kind,
                "rows": int(fires.sum()),
                "exclusion": criterion.kind == EXCLUSION,
            }
        )
    return rules, warnings


def audit(frame: pd.DataFrame, config: dict[str, Any] | None = None) -> QualityReport:
    """Score ``frame`` and list what is wrong with it, column by column."""
    completeness, missing = _completeness(frame)
    uniqueness, duplicates = _uniqueness(frame)
    consistency, inconsistent, consistency_warnings = _consistency(frame)
    uniformity, non_uniform = _uniformity(frame)
    validity, outliers = _validity(frame)
    clinical, rule_warnings = _clinical_rules(frame, config)

    scores = {
        "completeness": completeness,
        "uniqueness": uniqueness,
        "consistency": consistency,
        "uniformity": uniformity,
        "validity": validity,
    }
    labels = {
        "completeness": "Completeness (no missing values)",
        "uniqueness": "Uniqueness (no duplicate rows)",
        "consistency": "Consistency (values hold what their column says)",
        "uniformity": "Uniformity (one spelling per category)",
        "validity": "Statistical validity (no values outside the IQR fences)",
    }
    dimensions = [
        {
            "key": key,
            "label": labels[key],
            "score": round(scores[key], 4),
            "weight": weight,
            "band": _band(scores[key]),
        }
        for key, weight in _WEIGHTS
    ]
    total = sum(scores[key] * weight for key, weight in _WEIGHTS)

    warnings = [*consistency_warnings, *rule_warnings]
    if duplicates["rows"]:
        warnings.append(
            f"{duplicates['rows']} duplicated row(s): a duplicate inflates every N in the study"
        )
    for issue in non_uniform:
        warnings.append(
            f"column '{issue['column']}' writes {issue['variants']} categor"
            f"{'y' if issue['variants'] == 1 else 'ies'} more than one way "
            f"({issue['example']}); they will be analysed as different values"
        )

    return QualityReport(
        rows=len(frame),
        columns=int(frame.shape[1]),
        score=round(float(total), 4),
        band=_band(total),
        dimensions=dimensions,
        missing=missing,
        duplicates=duplicates,
        inconsistent=inconsistent,
        non_uniform=non_uniform,
        outliers=outliers,
        clinical_rules=clinical,
        warnings=warnings,
    )
