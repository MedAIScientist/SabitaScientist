"""Background AI jobs: record them, finish or fail them, list them for their owner.

Every AI feature that works in the background goes through :func:`run_tracked`,
so the user always gets one of two outcomes: a link to the result, or a readable
reason it failed. Before this, failures were swallowed and the user was left
guessing whether anything had happened.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db, get_db_path
from ..models import AiJob

logger = logging.getLogger(__name__)

_COLUMNS = (
    "id, kind, title, user_id, project_id, publication_id, status, "
    "result_path, error, created_at, finished_at"
)


class AiJobError(Exception):
    """A failure whose message is fit to show the user as-is."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_job(row) -> AiJob:
    return AiJob(**{k: row[k] for k in row.keys()})


def create_job(
    db_path: Path,
    *,
    kind: str,
    title: str,
    user_id: str,
    project_id: str | None = None,
    publication_id: str | None = None,
) -> AiJob:
    job_id = uuid.uuid4().hex
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO ai_jobs (id, kind, title, user_id, project_id, publication_id, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'running', ?)",
            (job_id, kind, title, user_id, project_id, publication_id, _now()),
        )
    return get_job(db_path, job_id)  # type: ignore[return-value]


def get_job(db_path: Path, job_id: str) -> AiJob | None:
    with get_db(db_path) as conn:
        row = conn.execute(f"SELECT {_COLUMNS} FROM ai_jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def list_jobs(
    db_path: Path,
    *,
    user_id: str,
    project_id: str | None = None,
    publication_id: str | None = None,
    limit: int = 20,
) -> list[AiJob]:
    """The caller's own jobs, newest first, optionally narrowed to one project or paper."""
    sql = f"SELECT {_COLUMNS} FROM ai_jobs WHERE user_id = ?"
    params: list = [user_id]
    if project_id:
        sql += " AND project_id = ?"
        params.append(project_id)
    if publication_id:
        sql += " AND publication_id = ?"
        params.append(publication_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_db(db_path) as conn:
        return [_row_to_job(r) for r in conn.execute(sql, params).fetchall()]


def _finish(db_path: Path, job_id: str, *, status: str, result_path: str | None, error: str | None) -> None:
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE ai_jobs SET status = ?, result_path = ?, error = ?, finished_at = ? WHERE id = ?",
            (status, result_path, error, _now(), job_id),
        )


def fail_stale_jobs(db_path: Path) -> int:
    """Jobs still 'running' when the server starts died with the previous process."""
    with get_db(db_path) as conn:
        cur = conn.execute(
            "UPDATE ai_jobs SET status = 'failed', error = ?, finished_at = ? WHERE status = 'running'",
            ("The server restarted before this job finished. Please start it again.", _now()),
        )
    return cur.rowcount


async def run_tracked(job_id: str, work: Callable[[], Awaitable[str | None]]) -> None:
    """Run a background job and record how it ended.

    ``work`` returns the UI path of what it produced, or ``None`` when the model
    produced nothing usable.
    """
    db = get_db_path()
    try:
        result_path = await work()
    except AiJobError as exc:
        _finish(db, job_id, status="failed", result_path=None, error=str(exc))
        return
    except Exception:
        logger.exception("AI job %s failed", job_id)
        _finish(db, job_id, status="failed", result_path=None,
                error="Something went wrong while running this job. The error has been logged.")
        return
    if result_path is None:
        _finish(db, job_id, status="failed", result_path=None,
                error="The AI returned no text. Try again, or rephrase the request.")
        return
    _finish(db, job_id, status="done", result_path=result_path, error=None)
