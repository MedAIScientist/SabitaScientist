"""Transformations that write a new version: a derived variable, a row subset.

Both go through one write path (``gazzali.crud.cohort.record_step``) so that every
change of the rows is one link of the hash chain and can be replayed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .vendor.core.expressions import UnsafeExpressionError, column_references, evaluate
from .vendor.core.fingerprint import ROW_ID, ranges_to_ids

__all__ = ["TransformError", "derive", "filter_rows"]


class TransformError(ValueError):
    """The requested transformation cannot be applied to this version."""


_RESERVED = {ROW_ID}


def derive(
    frame: pd.DataFrame, name: str, expression: str, *, overwrite: bool = False
) -> pd.DataFrame:
    """``frame`` with a column ``name`` computed by the sandboxed expression language.

    The expression sees the frame as ``df`` (``df['weight_kg'] / (df['height_cm']/100)**2``)
    and a restricted ``np``/``pd`` facade; it cannot import, open files or reach the
    network. An invalid expression raises ``TransformError`` before anything is written.
    """
    target = (name or "").strip()
    if not target:
        raise TransformError("a derived variable needs a name")
    if target in _RESERVED:
        raise TransformError(f"'{target}' is reserved for row identity")
    if target in frame.columns and not overwrite:
        raise TransformError(f"column '{target}' already exists")
    spec = (expression or "").strip()
    if not spec:
        raise TransformError("a derived variable needs an expression")

    missing = sorted(c for c in column_references(spec) if c not in frame.columns)
    if missing:
        raise TransformError(
            "the expression reads columns that are not in this version: "
            + ", ".join(missing)
        )
    try:
        values = evaluate(spec, frame)
    except UnsafeExpressionError as exc:
        raise TransformError(f"the expression was rejected: {exc}") from exc
    except Exception as exc:
        raise TransformError(f"the expression could not be evaluated: {exc}") from exc

    if isinstance(values, pd.Series):
        if len(values) != len(frame):
            raise TransformError(
                f"the expression returned {len(values)} values for {len(frame)} rows"
            )
        series = values.set_axis(frame.index)
    else:
        array = np.asarray(values)
        if array.ndim == 0:
            array = np.repeat(array, len(frame))
        if array.shape != (len(frame),):
            raise TransformError(
                f"the expression returned shape {array.shape}; a column needs ({len(frame)},)"
            )
        series = pd.Series(array, index=frame.index, name=target)

    out = frame.copy()
    out[target] = series
    return out


def filter_rows(
    frame: pd.DataFrame,
    *,
    action: str,
    row_ids: list[list[int]] | None = None,
) -> tuple[pd.DataFrame, int]:
    """Keep or drop the listed rows (inclusive ``[first, last]`` id ranges).

    Returns the new frame and the number of rows removed. Filtering never mutates a
    version: it writes a new one, and the removed ids are recorded in the trace.
    """
    if action not in ("keep", "drop"):
        raise TransformError("action must be 'keep' or 'drop'")
    selected = ranges_to_ids(row_ids or [])
    if selected.size == 0:
        raise TransformError("no rows were selected")
    unknown = set(np.setdiff1d(selected, frame.index.to_numpy()))
    if unknown:
        raise TransformError(
            f"{len(unknown)} selected row id(s) are not in this version"
        )

    mask = frame.index.isin(selected)
    out = frame.loc[mask] if action == "keep" else frame.loc[~mask]
    if out.empty:
        raise TransformError("the filter would leave no rows in the table")
    return out, int(len(frame) - len(out))


def summarize_change(before: pd.DataFrame, after: pd.DataFrame) -> dict[str, Any]:
    """The row/column counts the participant flow draws its boxes from."""
    return {
        "rows_in": len(before),
        "rows_out": len(after),
        "rows_removed": max(0, int(len(before) - len(after))),
        "rows_added": max(0, int(len(after) - len(before))),
        "columns_in": int(before.shape[1]),
        "columns_out": int(after.shape[1]),
    }
