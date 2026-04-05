"""Asyncio task registry for EvoScientist agent runs with queue-based SSE streaming."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# Per-run asyncio queues: run_id → Queue of {type, data} dicts
# None sentinel in the queue signals end of stream.
_run_queues: dict[str, asyncio.Queue[dict | None]] = {}
_run_tasks: dict[str, asyncio.Task] = {}

# Prompt prefixes guide the main agent to delegate to the correct sub-agent
AGENT_PROMPTS: dict[str, str] = {
    "research": (
        "Use the research-agent sub-agent to complete the following task. "
        "Return concise, actionable findings with sources.\n\nTask: "
    ),
    "code": (
        "Use the code-agent sub-agent to implement the following. "
        "Write clean, reproducible code with minimal dependencies.\n\nTask: "
    ),
    "data_analysis": (
        "Use the data-analysis-agent sub-agent to analyze and report on the following. "
        "Include statistics and produce publication-ready figures where appropriate.\n\nTask: "
    ),
    "writing": (
        "Use the writing-agent sub-agent to draft a paper-ready Markdown report for the following. "
        "Do not fabricate results or citations.\n\nTask: "
    ),
}


async def start_run(
    run_id: str, agent_type: str, prompt: str, workspace_dir: str
) -> None:
    """Start an agent run as a background asyncio task."""
    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    _run_queues[run_id] = queue
    task = asyncio.create_task(
        _run_agent(run_id, agent_type, prompt, workspace_dir, queue)
    )
    _run_tasks[run_id] = task


async def _run_agent(
    run_id: str,
    agent_type: str,
    prompt: str,
    workspace_dir: str,
    queue: asyncio.Queue,
) -> None:
    """Execute the agent and push token/status events into the queue."""
    # Lazy import so runner can start without loading the full EvoScientist stack
    from langchain_core.messages import AIMessage, AIMessageChunk

    from EvoScientist.EvoScientist import create_cli_agent

    prefix = AGENT_PROMPTS.get(agent_type, "")
    full_prompt = f"{prefix}{prompt}"

    Path(workspace_dir).mkdir(parents=True, exist_ok=True)

    try:
        agent = create_cli_agent(workspace_dir=workspace_dir)

        async for chunk in agent.astream(
            {"messages": [{"role": "user", "content": full_prompt}]},
            config={"configurable": {"thread_id": run_id}},
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            if not isinstance(chunk, tuple) or len(chunk) != 3:
                continue
            _, mode_str, data = chunk
            if mode_str != "messages":
                continue
            msg = data[0] if isinstance(data, tuple) and len(data) >= 1 else None
            if msg is None:
                continue
            if not isinstance(msg, (AIMessage, AIMessageChunk)):
                continue

            raw = msg.content
            if isinstance(raw, str):
                text = raw
            elif isinstance(raw, list):
                text = "".join(
                    b.get("text", "") if isinstance(b, dict) else ""
                    for b in raw
                )
            else:
                text = ""

            # Skip empty chunks and tool-selector JSON
            if text and not text.lstrip().startswith('{"tools":'):
                await queue.put({"type": "token", "data": text})

        await queue.put({"type": "status", "data": "done"})

    except asyncio.CancelledError:
        await queue.put({"type": "status", "data": "cancelled"})
    except Exception as exc:
        logger.exception("Agent run %s failed", run_id)
        await queue.put({"type": "error", "data": str(exc)})
        await queue.put({"type": "status", "data": "failed"})
    finally:
        _run_tasks.pop(run_id, None)
        # Leave queue in _run_queues briefly so streaming client can drain it


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
