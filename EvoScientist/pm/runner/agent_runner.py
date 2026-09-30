"""Asyncio task registry for Groq-backed agent runs with queue-based SSE streaming.

Replaces the previous LangGraph-based agent runner with direct Groq API calls
via httpx streaming. Records observations via ``EvoScientist.memory`` when
runs complete.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Groq decommissions models on a schedule; a hardcoded name here or in settings is
# a time bomb that fails silently (the run just produces no output). Override per
# deployment with PM_RUNNER_MODEL.
DEFAULT_RUNNER_MODEL = "openai/gpt-oss-120b"

# Per-run asyncio queues: run_id → Queue of {type, data} dicts
_run_queues: dict[str, asyncio.Queue[dict | None]] = {}
_run_tasks: dict[str, asyncio.Task] = {}
_orphan_cleanup_done = False


def parse_stream_chunk(raw: str) -> tuple[str, dict | None]:
    """Read one Groq SSE payload: return (text delta, usage if present).

    Split out from the streaming loop because the stream's shape is the part that
    breaks: the usage-only final chunk carries ``"choices": []``, and the previous
    ``choices[0]`` indexing turned that into an ``IndexError`` that failed the whole
    run. Unparseable payloads yield no text rather than an exception.
    """
    try:
        chunk = json.loads(raw)
    except json.JSONDecodeError:
        return "", None
    usage = chunk.get("usage") or None
    choices = chunk.get("choices") or []
    if not choices:
        return "", usage
    content = (choices[0].get("delta") or {}).get("content") or ""
    return content, usage


def _record_ai_usage(
    *,
    task: str,
    run_id: str,
    model: str,
    user_id: str | None,
    project_id: str | None,
    publication_id: str | None,
    prompt: str,
    output: str,
    reported_usage: dict | None,
    duration_ms: int,
) -> None:
    """Store what this run consumed, without ever failing the run.

    The runner is a separate process writing to the same SQLite file as the API,
    so a busy or missing database must not turn a finished draft into an error.
    """
    from ..crud.ai_usage import UsageContext, record_usage_safely

    usage = reported_usage or {}
    context = UsageContext(
        task=task,
        user_id=user_id,
        project_id=project_id,
        publication_id=publication_id,
        run_id=run_id,
        source="agent",
    )
    if usage:
        record_usage_safely(
            context=context,
            model=model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            prompt_chars=len(prompt),
            output_chars=len(output),
            duration_ms=duration_ms,
        )
        return
    # The provider stayed silent (or the stream died early): record the character
    # counts and let the accounting layer mark the row as an estimate.
    record_usage_safely(
        context=context,
        model=model,
        prompt_chars=len(prompt),
        output_chars=len(output),
        duration_ms=duration_ms,
    )



def _cancel_orphaned_runs(db_path: str | None = None) -> None:
    """Mark any ``running`` or ``pending`` runs as ``failed`` — they died with the last server."""
    global _orphan_cleanup_done
    if _orphan_cleanup_done:
        return
    _orphan_cleanup_done = True
    try:
        from ..db import get_db

        if not db_path:
            from ..db import get_db_path
            db_path = str(get_db_path())
        from pathlib import Path as _Path
        with get_db(_Path(db_path)) as conn:
            for status in ("running", "pending"):
                cur = conn.execute(
                    "UPDATE runs SET status = 'failed', error = ?, finished_at = ? WHERE status = ?",
                    ("Server restarted — run cancelled", datetime.now(UTC).isoformat(), status),
                )
                if cur.rowcount:
                    logger.info("Cancelled %d orphaned %s run(s) after restart", cur.rowcount, status)
    except Exception as exc:
        logger.debug("Orphaned-run cleanup skipped: %s", exc)


_cancel_orphaned_runs()

AGENT_PROMPTS: dict[str, str] = {
    "research": (
        "You are a research agent. Complete the following task. "
        "Return concise, actionable findings with sources.\n\nTask: "
    ),
    "code": (
        "You are a code agent. Implement the following. "
        "Write clean, reproducible code with minimal dependencies.\n\nTask: "
    ),
    "data_analysis": (
        "You are a data analysis agent. Analyze and report on the following. "
        "Include statistics and produce publication-ready figures where appropriate.\n\nTask: "
    ),
    "writing": (
        "You are a writing agent. Draft a paper-ready Markdown report for the following. "
        "Do not fabricate results or citations.\n\nTask: "
    ),
}

_SYSTEM_PROMPTS: dict[str, str] = {
    "research": (
        "You are a thorough research agent. Provide well-structured findings "
        "with clear reasoning. Be precise and cite sources where possible."
    ),
    "code": (
        "You are a skilled software engineer. Write clean, well-structured "
        "code that solves the given problem. Include necessary imports and "
        "follow best practices."
    ),
    "data_analysis": (
        "You are a data scientist. Analyze data rigorously with appropriate "
        "statistical methods. Present results clearly with numbers, tables, "
        "and clear interpretations."
    ),
    "writing": (
        "You are an academic writer. Produce well-structured, publication-ready "
        "text. Use clear prose and proper academic tone. Never fabricate "
        "results or citations."
    ),
}

def _get_model() -> str:
    try:
        from ...config.settings import get_effective_config
        return get_effective_config().pm_runner_model or DEFAULT_RUNNER_MODEL
    except Exception:
        return DEFAULT_RUNNER_MODEL


def _get_groq_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is required for the Groq runner"
        )
    return key


async def start_run(
    run_id: str,
    agent_type: str,
    prompt: str,
    workspace_dir: str,
    task: str | None = None,
    user_id: str | None = None,
    project_id: str | None = None,
    publication_id: str | None = None,
) -> None:
    """Start an agent run as a background asyncio task."""
    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    _run_queues[run_id] = queue
    task_handle = asyncio.create_task(
        _run_agent(
            run_id,
            agent_type,
            prompt,
            workspace_dir,
            queue,
            task=task or agent_type,
            user_id=user_id,
            project_id=project_id,
            publication_id=publication_id,
        )
    )
    _run_tasks[run_id] = task_handle


async def _run_agent(
    run_id: str,
    agent_type: str,
    prompt: str,
    workspace_dir: str,
    queue: asyncio.Queue,
    task: str | None = None,
    user_id: str | None = None,
    project_id: str | None = None,
    publication_id: str | None = None,
) -> None:
    """Execute via Groq API streaming, record observations, push events."""
    from ...memory.observations.store import record_observation_file
    from ...memory.project import resolve_project_id
    from ...memory.types import MemoryScope, MemorySourceType, MemoryType

    prefix = AGENT_PROMPTS.get(agent_type, prompt)
    system_prompt = _SYSTEM_PROMPTS.get(agent_type, "")
    full_prompt = f"{prefix}{prompt}" if prefix != prompt else prompt

    Path(workspace_dir).mkdir(parents=True, exist_ok=True)

    api_key = _get_groq_api_key()
    accumulated_text: list[str] = []
    model_name = _get_model()
    # Groq reports usage only when it is asked to, and only in the final chunk.
    # Without this the token counts are produced and thrown away.
    reported_usage: dict | None = None
    started = time.monotonic()

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt},
            ],
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": 0.3,
            "max_tokens": 4096,
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=30.0)
        ) as client:
            async with client.stream(
                "POST",
                f"{_GROQ_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        continue
                    content, usage = parse_stream_chunk(data_str)
                    if usage:
                        reported_usage = usage
                    if content:
                        accumulated_text.append(content)
                        await queue.put({"type": "token", "data": content})

        await queue.put({"type": "status", "data": "done"})

        output_text = "".join(accumulated_text)
        _record_ai_usage(
            task=task or agent_type,
            run_id=run_id,
            model=model_name,
            user_id=user_id,
            project_id=project_id,
            publication_id=publication_id,
            prompt=full_prompt,
            output=output_text,
            reported_usage=reported_usage,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

        # Record observation via EvoScientist.memory
        output_text = "".join(accumulated_text)
        if output_text.strip():
            try:
                mem_dir = Path(workspace_dir) / ".memory"
                project_id = resolve_project_id(workspace=workspace_dir)
                record_observation_file(
                    memory_dir=str(mem_dir),
                    project_id=project_id,
                    memory_type=MemoryType.SEMANTIC,
                    summary=f"PM agent run: {run_id}",
                    observation=output_text[:2000],
                    why_it_matters=f"{agent_type} agent output for project {project_id}",
                    scope=MemoryScope.PROJECT,
                    source_type=MemorySourceType.TURN,
                    source_session_id=run_id,
                    source_agent=agent_type,
                )
            except Exception as obs_err:
                logger.debug("Observation recording skipped: %s", obs_err)

    except asyncio.CancelledError:
        await queue.put({"type": "status", "data": "cancelled"})
    except Exception as exc:
        logger.exception("Agent run %s failed", run_id)
        await queue.put({"type": "error", "data": str(exc)})
        await queue.put({"type": "status", "data": "failed"})
    finally:
        _run_tasks.pop(run_id, None)


async def stream_events(run_id: str) -> AsyncGenerator[dict, None]:
    """Yield events from the run queue until a terminal status event."""
    queue = _run_queues.get(run_id)
    if queue is None:
        yield {"type": "error", "data": "Run not found or already completed"}
        yield {"type": "status", "data": "failed"}
        return

    try:
        while True:
            event = await queue.get()
            yield event
            if event.get("type") == "status":
                break
    finally:
        _run_queues.pop(run_id, None)


async def cancel(run_id: str) -> bool:
    """Cancel an in-progress run. Returns True if a task was cancelled."""
    task = _run_tasks.pop(run_id, None)
    if task and not task.done():
        task.cancel()
        return True
    return False
