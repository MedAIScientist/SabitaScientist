"""Parse uploaded result files into structured metric rows.

Two CSV shapes are recognized:

Long
    A ``metric``/``name`` column plus a ``value`` column — one metric per row.

Wide
    Every numeric column is a metric; an optional label column
    (``split``/``model``/``condition``/...) names the row. This is what
    ``DataFrame.to_csv()`` usually produces.

Anything that does not parse cleanly yields no metrics at all. That is
deliberate: a number that never reaches the table is a number the paper
drafter never sees, and missing beats invented.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_NAME_COLS = ("metric", "metric_name", "name")
_VALUE_COLS = ("value", "score", "result")
_UNIT_COLS = ("unit", "units")
_LABEL_COLS = ("split", "model", "condition", "group", "run", "fold", "dataset", "arm")
_N_COLS = ("n", "count", "n_samples", "num_samples")
_STDERR_COLS = ("stderr", "std_err", "sem", "se", "std", "stdev")

# ponytail: hard cap so one huge CSV cannot flood the drafting prompt
MAX_METRICS = 2000


@dataclass(frozen=True)
class ParsedMetric:
    """One recorded number, with whatever context the file supplied."""

    name: str
    value: float
    unit: str | None = None
    split: str | None = None
    n: int | None = None
    stderr: float | None = None


def is_parseable(filename: str, content_type: str) -> bool:
    """True if this upload looks like a delimited results table."""
    lowered = filename.lower()
    return lowered.endswith((".csv", ".tsv")) or content_type in (
        "text/csv",
        "text/tab-separated-values",
    )


def parse_metrics_csv(text: str) -> list[ParsedMetric]:
    """Extract metrics from CSV/TSV text. Returns [] if nothing parses."""
    try:
        reader = csv.DictReader(io.StringIO(text), delimiter=_sniff_delimiter(text))
        fields = [f for f in (reader.fieldnames or []) if f]
        if not fields:
            return []
        name_col = _pick(fields, _NAME_COLS)
        value_col = _pick(fields, _VALUE_COLS)
        unit_col = _pick(fields, _UNIT_COLS)
        label_col = _pick(fields, _LABEL_COLS)
        n_col = _pick(fields, _N_COLS)
        stderr_col = _pick(fields, _STDERR_COLS)
        rows = list(reader)
    except (csv.Error, UnicodeDecodeError) as exc:
        logger.warning("Could not parse metrics file: %s", exc)
        return []

    if name_col and value_col:
        metrics = _parse_long(rows, name_col, value_col, unit_col, label_col, n_col, stderr_col)
    else:
        metrics = _parse_wide(rows, fields, unit_col, label_col, n_col, stderr_col)
    return metrics[:MAX_METRICS]


def _sniff_delimiter(text: str) -> str:
    header = text.split("\n", 1)[0]
    return "\t" if header.count("\t") > header.count(",") else ","


def _pick(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {f.strip().lower(): f for f in fieldnames}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def _num(raw: str | None) -> float | None:
    """Strict float parse.

    Thousands separators and ``12%`` are rejected on purpose — an ambiguously
    parsed number is worse than a missing one.
    """
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except ValueError:
        return None


def _text(row: dict, col: str | None) -> str | None:
    if not col:
        return None
    return (row.get(col) or "").strip() or None


def _int(row: dict, col: str | None) -> int | None:
    if not col:
        return None
    value = _num(row.get(col))
    return int(value) if value is not None else None


def _parse_long(
    rows: list[dict],
    name_col: str,
    value_col: str,
    unit_col: str | None,
    label_col: str | None,
    n_col: str | None,
    stderr_col: str | None,
) -> list[ParsedMetric]:
    metrics = []
    for row in rows:
        name = (row.get(name_col) or "").strip()
        value = _num(row.get(value_col))
        if not name or value is None:
            continue
        metrics.append(
            ParsedMetric(
                name=name,
                value=value,
                unit=_text(row, unit_col),
                split=_text(row, label_col),
                n=_int(row, n_col),
                stderr=_num(row.get(stderr_col)) if stderr_col else None,
            )
        )
    return metrics


def _parse_wide(
    rows: list[dict],
    fields: list[str],
    unit_col: str | None,
    label_col: str | None,
    n_col: str | None,
    stderr_col: str | None,
) -> list[ParsedMetric]:
    reserved = {c for c in (unit_col, label_col, n_col, stderr_col) if c}
    metrics = []
    for index, row in enumerate(rows):
        split = _text(row, label_col)
        if split is None and len(rows) > 1:
            split = f"row {index + 1}"
        n = _int(row, n_col)
        stderr = _num(row.get(stderr_col)) if stderr_col else None
        for field in fields:
            if field in reserved:
                continue
            value = _num(row.get(field))
            if value is None:
                continue
            metrics.append(
                ParsedMetric(
                    name=field.strip(),
                    value=value,
                    unit=_text(row, unit_col),
                    split=split,
                    n=n,
                    stderr=stderr,
                )
            )
    return metrics
