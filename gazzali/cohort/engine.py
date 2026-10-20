"""Orchestration: version → population → analysis, and the participant flow.

This module is the boundary between the database and the statistics. It imports no
FastAPI and no SQLite: everything here takes plain data and returns plain data, so
the same code can run in a worker process when the cohort outgrows the API process.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pandas as pd

from . import analyses, store
from .vendor.core.attrition import (
    AnalysisCount,
    ParticipantFlow,
    SourceRows,
    participant_flow,
)
from .vendor.core.fingerprint import frame_fingerprint
from .vendor.core.population import (
    PopulationResult,
    active_criteria,
    catalogue,
    evaluate_population,
)

__all__ = [
    "EngineError",
    "build_flow",
    "catalogue_payload",
    "evaluate",
    "load_frame",
    "population_frame",
    "run",
]

# Analysis methods the engine dispatches to.
_METHODS = (
    "descriptive",
    "table1",
    "compare",
    "survival",
    "cox",
    "diagnostic",
    "ratio2x2",
    "logistic",
    "mantel_haenszel",
    "agreement",
    "mcar",
    "multiple_imputation",
    "power",
)


class EngineError(ValueError):
    """The request cannot be executed against this version."""


def load_frame(version: Any) -> pd.DataFrame:
    """Read a version's rows, verifying its recorded content hash first."""
    try:
        return store.read_version(
            version.rel_path, expected_sha256=version.content_sha256
        )
    except store.CohortStoreError as exc:
        raise EngineError(str(exc)) from exc


def evaluate(
    frame: pd.DataFrame, config: dict[str, Any] | None, ticked: list[str]
) -> PopulationResult:
    """Apply the ticked criteria; the result identifies the rows it kept."""
    criteria = active_criteria(config, ticked)
    known = {c.id for c in catalogue(config)}
    unknown = sorted(set(ticked) - known)
    if unknown:
        raise EngineError(
            "unknown criteria: "
            + ", ".join(unknown)
            + " (the study configuration changed)"
        )
    return evaluate_population(
        frame, criteria, data_fp=frame_fingerprint(frame, index=True)
    )


def population_frame(frame: pd.DataFrame, result: PopulationResult) -> pd.DataFrame:
    """The rows the population kept. A population never deletes rows from the table."""
    if not result.ok:
        raise EngineError(
            "the analysis population could not be evaluated: "
            + "; ".join(f"{key}: {value}" for key, value in result.errors.items())
        )
    if result.n_included == 0:
        raise EngineError(
            "the analysis population is empty: no row satisfies the criteria"
        )
    return frame.loc[result.included]


def run(
    frame: pd.DataFrame,
    method: str,
    params: dict[str, Any],
    *,
    dictionary: dict[str, Any] | None = None,
) -> analyses.AnalysisOutcome:
    """Dispatch one analysis on the population-restricted frame."""
    if method not in _METHODS:
        raise EngineError(
            f"unknown method {method!r}; expected one of {', '.join(_METHODS)}"
        )
    dictionary = dictionary or {}
    try:
        if method == "descriptive":
            return analyses.descriptive(
                frame,
                list(params.get("variables") or []),
                dictionary=dictionary,
                summary=str(params.get("summary") or "auto"),
            )
        if method == "table1":
            return analyses.table_one(
                frame,
                list(params.get("variables") or []),
                group=params.get("group") or None,
                dictionary=dictionary,
                summary=str(params.get("summary") or "auto"),
                adjust_method=str(params.get("adjust") or "holm"),
                alpha=float(params.get("alpha") or 0.05),
            )
        if method == "compare":
            outcome = str(params.get("outcome") or "")
            group = str(params.get("group") or "")
            if not outcome or not group:
                raise EngineError(
                    "a comparison needs both an outcome and a group column"
                )
            return analyses.compare(
                frame,
                outcome,
                group=group,
                kind=str(params.get("kind") or "auto"),
                alpha=float(params.get("alpha") or 0.05),
                dictionary=dictionary,
            )
        if method == "survival":
            return analyses.survival(
                frame,
                time=str(params.get("time") or ""),
                event=str(params.get("event") or ""),
                group=params.get("group") or None,
                alpha=float(params.get("alpha") or 0.05),
            )
        if method == "cox":
            return analyses.cox(
                frame,
                time=str(params.get("time") or ""),
                event=str(params.get("event") or ""),
                covariates=list(params.get("covariates") or []),
                alpha=float(params.get("alpha") or 0.05),
            )
        if method == "diagnostic":
            cutoff = params.get("cutoff")
            return analyses.diagnostic(
                frame,
                test=str(params.get("test") or ""),
                outcome=str(params.get("outcome") or ""),
                cutoff=None if cutoff is None else float(cutoff),
                pos_label=params.get("pos_label") or None,
                alpha=float(params.get("alpha") or 0.05),
            )
        if method == "ratio2x2":
            return analyses.ratio_2x2(
                frame,
                exposure=str(params.get("exposure") or ""),
                outcome=str(params.get("outcome") or ""),
                alpha=float(params.get("alpha") or 0.05),
            )
        if method == "logistic":
            return analyses.logistic(
                frame,
                outcome=str(params.get("outcome") or ""),
                covariates=list(params.get("covariates") or []),
                event_level=params.get("event_level") or None,
                alpha=float(params.get("alpha") or 0.05),
            )
        if method == "mantel_haenszel":
            return analyses.mantel_haenszel(
                frame,
                exposure=str(params.get("exposure") or ""),
                outcome=str(params.get("outcome") or ""),
                stratum=str(params.get("stratum") or ""),
                alpha=float(params.get("alpha") or 0.05),
            )
        if method == "agreement":
            return analyses.agreement(
                frame,
                raters=list(params.get("raters") or []),
                measure=str(params.get("measure") or "icc"),
                weights=params.get("weights") or None,
                icc_model=str(params.get("icc_model") or "ICC(2,1)"),
                alpha=float(params.get("alpha") or 0.05),
            )
        if method == "power":
            effect = params.get("effect")
            return analyses.power(
                frame,
                outcome=str(params.get("outcome") or ""),
                group=str(params.get("group") or ""),
                effect=None if effect is None else float(effect),
                target_power=float(params.get("target_power") or 0.8),
                alpha=float(params.get("alpha") or 0.05),
            )
        if method == "mcar":
            return analyses.mcar(
                frame,
                variables=list(params.get("variables") or []) or None,
                alpha=float(params.get("alpha") or 0.05),
            )
        if method == "multiple_imputation":
            return analyses.multiple_imputation(
                frame,
                target=str(params.get("target") or ""),
                variables=list(params.get("variables") or []) or None,
                outcome=params.get("outcome") or None,
                group=params.get("group") or None,
                covariates=list(params.get("covariates") or []) or None,
                time=params.get("time") or None,
                event=params.get("event") or None,
                kind=str(params.get("kind") or "welch"),
                m=int(params.get("m") or 20),
                maxit=int(params.get("maxit") or 10),
                seed=params.get("seed"),
                alpha=float(params.get("alpha") or 0.05),
            )
    except analyses.AnalysisError as exc:
        raise EngineError(str(exc)) from exc
    raise EngineError(f"unknown method {method!r}")


def catalogue_payload(config: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every criterion of the configuration, for the tick list in the UI."""
    return [
        {
            "id": c.id,
            "family": c.family,
            "kind": c.kind,
            "name": c.name,
            "description": c.description,
            "columns": list(c.columns),
        }
        for c in catalogue(config)
    ]


def build_flow(
    result: PopulationResult,
    *,
    dataset: str,
    n_loaded: int | None = None,
    source: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
    analyses_: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The STROBE participant flow (item 13), with its own consistency check.

    ``inconsistencies`` is returned rather than raised: a flow that does not add up is
    a finding about the trace, and the reader must see it.
    """
    flow: ParticipantFlow = participant_flow(
        result,
        dataset=dataset,
        source=SourceRows(**source) if source else None,
        n_loaded=n_loaded,
        steps=steps or [],
        analyses=[AnalysisCount(**item) for item in (analyses_ or [])],
    )
    return {**flow.to_dict(), "inconsistencies": flow.inconsistencies()}


def population_record(result: PopulationResult) -> dict[str, Any]:
    """The population row, ready for the database."""
    return {
        "criteria_json": [c.snapshot() for c in result.criteria],
        "stages_json": [asdict(stage) for stage in result.stages],
        "counts_json": [
            {
                "id": count.criterion.id,
                "family": count.criterion.family,
                "name": count.criterion.name,
                "kind": count.criterion.kind,
                "marginal_base": count.marginal_base,
                "marginal_in_stage": count.marginal_in_stage,
                "sequential": count.sequential,
            }
            for count in result.counts
        ],
        "n_base": result.n_base,
        "n_included": result.n_included,
        "fingerprint": result.fingerprint,
    }
