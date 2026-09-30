"""AI usage accounting: what each LLM call consumed, and for whose work.

Nothing here is an optimisation by itself — it is the measurement that makes
optimisation possible. Every call records the task that asked for it, the model
that served it, and the tokens it burned, attributed to a user, project and (when
applicable) publication.

Two callers write rows: the direct path in ``pm/_ai.py`` and the agent runner in
``pm/runner/agent_runner.py`` (a separate process, hence its own connection).

Honesty rule: providers do not always report token counts. When they do not, the
row is stored with ``token_source='estimated'`` and derived from character counts.
:func:`summarize_usage` keeps the two sums apart so an estimate is never presented
as a measurement.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..db import get_db
from ..models import AI_USAGE_SOURCES, AI_USAGE_TOKEN_SOURCES, AiUsage

# Rough English/code ratio for the fallback estimate. Deliberately conservative:
# under-reporting an estimate is safer than inventing precision.
_CHARS_PER_TOKEN = 4


@dataclass
class UsageContext:
    """Who and what an LLM call belongs to.

    ``task`` is the label that makes a usage report actionable ("draft-section",
    "respond-to-reviewers", "generate-hypothesis"), so it is required.
    """

    task: str
    user_id: str | None = None
    project_id: str | None = None
    publication_id: str | None = None
    run_id: str | None = None
    source: str = "direct"


def estimate_tokens(text: str | None) -> int:
    """Token estimate for providers that do not report usage."""
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


def extract_usage(message: object) -> tuple[int | None, int | None, int | None]:
    """Pull (prompt, completion, total) tokens out of a provider response.

    LangChain surfaces usage in ``usage_metadata``; some providers only leave an
    OpenAI-style ``token_usage`` in ``response_metadata``. Returns ``None``s when
    the provider said nothing, so the caller can fall back to an estimate.
    """
    meta = getattr(message, "usage_metadata", None)
    if isinstance(meta, dict) and meta:
        return (
            meta.get("input_tokens"),
            meta.get("output_tokens"),
            meta.get("total_tokens"),
        )
    response_meta = getattr(message, "response_metadata", None)
    if isinstance(response_meta, dict):
        usage = response_meta.get("token_usage") or response_meta.get("usage") or {}
        if isinstance(usage, dict) and usage:
            return (
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                usage.get("total_tokens"),
            )
    return None, None, None


def record_usage(
    db_path: Path,
    *,
    context: UsageContext,
    model: str | None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    prompt_chars: int | None = None,
    output_chars: int | None = None,
    duration_ms: int | None = None,
) -> AiUsage:
    """Store one AI call. Falls back to an estimate when the provider was silent."""
    if context.source not in AI_USAGE_SOURCES:
        raise ValueError(f"Unknown AI usage source: {context.source}")

    if prompt_tokens is None and completion_tokens is None and total_tokens is None:
        token_source = "estimated"
        if prompt_chars is not None:
            prompt_tokens = max(1, prompt_chars // _CHARS_PER_TOKEN)
        if output_chars is not None:
            completion_tokens = max(1, output_chars // _CHARS_PER_TOKEN)
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
    else:
        token_source = "provider"
        if total_tokens is None:
            total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

    if token_source not in AI_USAGE_TOKEN_SOURCES:
        raise ValueError(f"Unknown token source: {token_source}")

    usage_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO ai_usage
               (id, user_id, project_id, publication_id, run_id, task, source, model,
                prompt_tokens, completion_tokens, total_tokens, token_source,
                prompt_chars, output_chars, duration_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                usage_id,
                context.user_id,
                context.project_id,
                context.publication_id,
                context.run_id,
                context.task,
                context.source,
                model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                token_source,
                prompt_chars,
                output_chars,
                duration_ms,
                now,
            ),
        )
    return AiUsage(
        id=usage_id,
        task=context.task,
        source=context.source,
        token_source=token_source,
        created_at=now,
        user_id=context.user_id,
        project_id=context.project_id,
        publication_id=context.publication_id,
        run_id=context.run_id,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        prompt_chars=prompt_chars,
        output_chars=output_chars,
        duration_ms=duration_ms,
    )


def record_usage_safely(db_path: Path | None = None, **kwargs) -> AiUsage | None:
    """Record usage without ever failing the work that produced it.

    The agent runner is a separate process writing to the same SQLite file, and a
    busy database must not turn a successful run into an error. A lost accounting
    row is acceptable; a lost paper draft is not.
    """
    import logging

    try:
        path = db_path if db_path is not None else _default_db_path()
        return record_usage(path, **kwargs)
    except Exception:  # pragma: no cover - defensive, exercised by design
        logging.getLogger(__name__).warning(
            "AI usage could not be recorded", exc_info=True
        )
        return None


def _default_db_path() -> Path:
    from ..db import get_db_path

    return get_db_path()


def _since_iso(days: int | None) -> str | None:
    if not days or days <= 0:
        return None
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def _filters(
    *,
    user_id: str | None = None,
    project_id: str | None = None,
    publication_id: str | None = None,
    days: int | None = None,
) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if publication_id:
        clauses.append("publication_id = ?")
        params.append(publication_id)
    since = _since_iso(days)
    if since:
        clauses.append("created_at >= ?")
        params.append(since)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def summarize_usage(
    db_path: Path,
    *,
    user_id: str | None = None,
    project_id: str | None = None,
    publication_id: str | None = None,
    days: int | None = 30,
) -> dict:
    """Aggregate usage: totals, and breakdowns by task, model and source.

    ``tokens.provider_reported`` and ``tokens.estimated`` are kept separate on
    purpose — adding them into one figure would present an estimate as a
    measurement.
    """
    where, params = _filters(
        user_id=user_id,
        project_id=project_id,
        publication_id=publication_id,
        days=days,
    )
    with get_db(db_path) as conn:
        totals = conn.execute(
            f"""SELECT COUNT(*) AS calls,
                       COALESCE(SUM(CASE WHEN token_source = 'provider'
                                         THEN total_tokens END), 0) AS provider_tokens,
                       COALESCE(SUM(CASE WHEN token_source = 'estimated'
                                         THEN total_tokens END), 0) AS estimated_tokens,
                       COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                       COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                       AVG(duration_ms) AS avg_duration_ms
                FROM ai_usage {where}""",
            params,
        ).fetchone()

        by_task = conn.execute(
            f"""SELECT task,
                       COUNT(*) AS calls,
                       COALESCE(SUM(CASE WHEN token_source = 'provider'
                                         THEN total_tokens END), 0) AS provider_tokens,
                       COALESCE(SUM(CASE WHEN token_source = 'estimated'
                                         THEN total_tokens END), 0) AS estimated_tokens
                FROM ai_usage {where}
                GROUP BY task
                ORDER BY provider_tokens + estimated_tokens DESC, calls DESC""",
            params,
        ).fetchall()

        by_model = conn.execute(
            f"""SELECT COALESCE(model, 'unknown') AS model,
                       COUNT(*) AS calls,
                       COALESCE(SUM(CASE WHEN token_source = 'provider'
                                         THEN total_tokens END), 0) AS provider_tokens,
                       COALESCE(SUM(CASE WHEN token_source = 'estimated'
                                         THEN total_tokens END), 0) AS estimated_tokens
                FROM ai_usage {where}
                GROUP BY COALESCE(model, 'unknown')
                ORDER BY provider_tokens + estimated_tokens DESC""",
            params,
        ).fetchall()

    return {
        "window_days": days,
        "calls": totals["calls"],
        "tokens": {
            "provider_reported": totals["provider_tokens"],
            "estimated": totals["estimated_tokens"],
            "prompt": totals["prompt_tokens"],
            "completion": totals["completion_tokens"],
        },
        "avg_duration_ms": (
            int(totals["avg_duration_ms"]) if totals["avg_duration_ms"] else None
        ),
        "by_task": [dict(r) for r in by_task],
        "by_model": [dict(r) for r in by_model],
    }


def list_usage(
    db_path: Path,
    *,
    user_id: str | None = None,
    project_id: str | None = None,
    publication_id: str | None = None,
    days: int | None = None,
    limit: int = 50,
) -> list[AiUsage]:
    """Most recent AI calls, newest first."""
    where, params = _filters(
        user_id=user_id,
        project_id=project_id,
        publication_id=publication_id,
        days=days,
    )
    params.append(max(1, min(limit, 500)))
    with get_db(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM ai_usage {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
    return [_row_to_usage(r) for r in rows]


def _row_to_usage(row) -> AiUsage:
    return AiUsage(
        id=row["id"],
        task=row["task"],
        source=row["source"],
        token_source=row["token_source"],
        created_at=row["created_at"],
        user_id=row["user_id"],
        project_id=row["project_id"],
        publication_id=row["publication_id"],
        run_id=row["run_id"],
        model=row["model"],
        prompt_tokens=row["prompt_tokens"],
        completion_tokens=row["completion_tokens"],
        total_tokens=row["total_tokens"],
        prompt_chars=row["prompt_chars"],
        output_chars=row["output_chars"],
        duration_ms=row["duration_ms"],
    )
