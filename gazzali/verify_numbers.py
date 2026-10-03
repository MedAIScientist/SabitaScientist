"""Verified result reporting for AI drafts (paper arXiv:2605.20025 §3.4).

Every number an AI draft states in a results-bearing section must match a value
that was actually recorded for the publication's experiments (``experiment_metrics``,
which includes AutoResearchClaw's verified registry). Unmatched numbers in those
sections are marked ``[UNVERIFIED]`` in the text; elsewhere they are only counted,
because an introduction legitimately quotes figures from the literature.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .db import get_db

TOLERANCE = 0.01  # relative, as ARC's VerifiedRegistry
STRICT_SECTIONS = ("abstract", "results", "experiments", "experiment", "evaluation")
MARK = " [UNVERIFIED]"

_NUMBER = re.compile(r"(?<![\w.\[])([-+]?\d+(?:[.,]\d+)?)(\s?%)?(?![\w\]])")
_NOT_A_RESULT_BEFORE = re.compile(
    r"(?:section|table|figure|fig\.|eq\.|equation|step|stage|phase|chapter|appendix|version|v)\s*$", re.IGNORECASE
)
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)$")


def recorded_values(db: Path, publication_id: str) -> list[float]:
    """Metrics of the experiments linked to the publication, else of its project."""
    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT m.value FROM experiment_metrics m
                 JOIN publication_experiments pe ON pe.experiment_id = m.experiment_id
                WHERE pe.publication_id = ?""",
            (publication_id,),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                """SELECT m.value FROM experiment_metrics m
                     JOIN experiments e ON e.id = m.experiment_id
                     JOIN publications p ON p.project_id = e.project_id
                    WHERE p.id = ?""",
                (publication_id,),
            ).fetchall()
    return [float(r[0]) for r in rows]


def is_verified(value: float, percent: bool, recorded: list[float]) -> bool:
    candidates = [value, value / 100] if percent else [value, value / 100, value * 100]
    for v in candidates:
        for m in recorded:
            if m == 0:
                if abs(v) < 1e-9:
                    return True
            elif abs(v - m) / abs(m) <= TOLERANCE:
                return True
    return False


def _checkable(text: str, match: re.Match) -> float | None:
    """The number if it is a result-like claim; None for years, counts, references."""
    raw, pct = match.group(1).replace(",", "."), match.group(2)
    try:
        value = float(raw)
    except ValueError:
        return None
    if _NOT_A_RESULT_BEFORE.search(text[max(0, match.start() - 12):match.start()]):
        return None
    if pct:
        return value
    if "." not in raw:
        if 1900 <= value <= 2100 or abs(value) < 10:
            return None  # a year, or a small count such as "5 seeds"
    return value


def verify(text: str, recorded: list[float], section: str | None = None) -> tuple[str, dict]:
    """Return (text with strict-section claims marked, summary).

    ``section`` names the section of a single-section draft; for a full draft the
    markdown headings decide which parts are strict.
    """
    strict_default = (section or "").lower() in STRICT_SECTIONS
    full_draft = section is None
    out_lines: list[str] = []
    checked = verified = 0
    unverified: list[dict] = []
    strict = strict_default
    for line in text.splitlines(keepends=True):
        heading = _HEADING.match(line)
        if heading and full_draft:
            strict = any(s in heading.group(2).lower() for s in STRICT_SECTIONS)
            out_lines.append(line)
            continue
        pieces: list[str] = []
        last = 0
        for m in _NUMBER.finditer(line):
            value = _checkable(line, m)
            if value is None:
                continue
            checked += 1
            if is_verified(value, bool(m.group(2)), recorded):
                verified += 1
                continue
            unverified.append({"value": m.group(0).strip(), "strict": strict,
                               "context": line[max(0, m.start() - 40):m.end() + 40].strip()})
            if strict:
                pieces.append(line[last:m.end()] + MARK)
                last = m.end()
        pieces.append(line[last:])
        out_lines.append("".join(pieces))
    summary = {
        "checked": checked,
        "verified": verified,
        "unverified": len(unverified),
        "unverified_in_results": sum(1 for u in unverified if u["strict"]),
        "examples": unverified[:20],
        "recorded_values": len(recorded),
    }
    return "".join(out_lines), summary


def verify_for_publication(db: Path, publication_id: str, text: str, section: str | None) -> tuple[str, str]:
    """Mark the draft and return (text, verification_json) for storage."""
    marked, summary = verify(text, recorded_values(db, publication_id), section)
    return marked, json.dumps(summary)
