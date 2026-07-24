"""Unified AI Copilot — uses the authenticated user for all tool operations."""

from __future__ import annotations

import json
import logging
import re as _re
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from EvoScientist.pm.models import User
from EvoScientist.tools.pm_tools import PM_TOOLS, current_user_id

from ....config.settings import get_effective_config
from ....llm.models import DEFAULT_MODEL, get_chat_model
from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_TOOL_ITERATIONS = 10


def _get_model(streaming: bool = True):
    config = get_effective_config()
    model_name = config.auxiliary_model or DEFAULT_MODEL
    return get_chat_model(model_name, temperature=0.3, streaming=streaming)


_TOOL_DESCRIPTIONS = "\n".join(
    f"- {t.name}({', '.join(t.args)}): {t.description.split(chr(10))[0]}"
    for t in PM_TOOLS
)


def _build_system_prompt(context: dict | None = None) -> str:
    ctx = context or {}
    page = ctx.get("page", "")
    project_id = ctx.get("project_id", "")
    parts = [
        "You are an AI research assistant for the Gazzali Project Management platform.",
        "You have access to tools. When you need to use a tool, respond with EXACTLY:",
        "",
        'TOOL_CALL: tool_name(param1="value1", param2="value2")',
        "",
        "Then wait for the tool result before continuing.",
        "Available tools:",
        _TOOL_DESCRIPTIONS,
        "",
        "IMPORTANT:",
        "- The pm_create_project tool auto-detects templates from the project name (ML keywords → ml-research).",
        "- NEVER include lab_id when calling pm_create_project unless the user explicitly names a lab.",
        "- When creating a task, ensure the project_id is valid.",
        "- If you get an error, check what data is available and retry with correct parameters.",
        "",
        "If you don't need a tool, respond normally in natural language.",
        "Be concise and proactive.",
    ]
    if page:
        parts.insert(1, f"The user is on page: {page}")
    if project_id:
        parts.insert(1, f"Active project ID: {project_id}")
    return "\n".join(parts)


def _parse_tool_call(text: str):
    m = _re.search(
        r"TOOL_CALL:\s*(\w+)\(([^)]*)\)\s*$",
        text.strip(),
        _re.MULTILINE | _re.DOTALL,
    )
    if not m:
        return None
    name = m.group(1)
    args_str = m.group(2).strip()
    args: dict[str, Any] = {}
    if args_str:
        for pair in _re.findall(r'(\w+)=("[^"]*"|\'[^\']*\'|[\w\.-]+)', args_str):
            k, v = pair
            v = v.strip("\"'")
            args[k] = v
    return name, args


async def _execute_tool(name: str, args: dict) -> str:
    found = next((t for t in PM_TOOLS if t.name == name), None)
    if not found:
        return f"Error: tool '{name}' not found."
    try:
        result = await found.ainvoke(args)
        return str(result)
    except Exception as exc:
        return f"Error: {exc}"


async def _run_tool_loop(
    session_id: str,
    user_message: str,
    user_id: str,
    context: dict | None = None,
) -> AsyncGenerator[str, None]:
    token = current_user_id.set(user_id)
    try:
        model = _get_model(streaming=True)
        system_prompt = _build_system_prompt(context)
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        for iteration in range(_MAX_TOOL_ITERATIONS):
            accumulated = ""
            async for chunk in model.astream(messages):
                content = chunk.content if hasattr(chunk, "content") else ""
                if content:
                    accumulated += content

            parsed = _parse_tool_call(accumulated)

            if not parsed:
                yield f"data: {json.dumps({'type': 'token', 'data': accumulated})}\n\n"
                yield f"data: {json.dumps({'type': 'status', 'data': 'done'})}\n\n"
                return

            name, args = parsed
            visible = _re.sub(r"\nTOOL_CALL:\s*\w+\([^)]*\)\s*$", "", accumulated.strip(), flags=_re.MULTILINE)
            if visible:
                yield f"data: {json.dumps({'type': 'token', 'data': visible})}\n\n"

            yield f"data: {json.dumps({'type': 'tool_start', 'data': name})}\n\n"
            result = await _execute_tool(name, args)
            yield f"data: {json.dumps({'type': 'tool_end', 'data': result[:200]})}\n\n"

            messages.append({"role": "assistant", "content": accumulated})
            messages.append({"role": "user", "content": f"Tool result for {name}:\n{result}\n\nSummarize for the user."})

        yield f"data: {json.dumps({'type': 'error', 'data': 'Max iterations reached.'})}\n\n"
        yield f"data: {json.dumps({'type': 'status', 'data': 'done'})}\n\n"
    finally:
        current_user_id.reset(token)


class CopilotRequest(BaseModel):
    message: str
    session_id: str = ""
    context: dict | None = None


@router.post("/copilot/stream")
async def copilot_stream(body: CopilotRequest, user: User = Depends(get_current_user)):
    session_id = body.session_id or str(uuid.uuid4())
    return StreamingResponse(
        _run_tool_loop(session_id, body.message, user.id, body.context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
        },
    )


@router.post("/copilot")
async def copilot_sync(body: CopilotRequest, user: User = Depends(get_current_user)):
    session_id = body.session_id or str(uuid.uuid4())
    token = current_user_id.set(user.id)
    try:
        model = _get_model(streaming=False)
        system_prompt = _build_system_prompt(body.context)
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": body.message},
        ]

        for iteration in range(_MAX_TOOL_ITERATIONS):
            result = await model.ainvoke(messages)
            text = result.content if hasattr(result, "content") else str(result)

            parsed = _parse_tool_call(text)
            if not parsed:
                return {"response": text, "session_id": session_id}

            name, args = parsed
            tool_result = await _execute_tool(name, args)
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": f"Tool result for {name}:\n{tool_result}\n\nSummarize for the user."})

        return {"response": "Max iterations reached.", "session_id": session_id}
    except Exception as exc:
        logger.exception("Copilot sync error")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        current_user_id.reset(token)
