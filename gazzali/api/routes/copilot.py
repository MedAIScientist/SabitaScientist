"""AI copilot: a streamed chat that can read and (with confirmation) change PM data.

Design, from the user's side:

* Native tool calling (``bind_tools``): arguments arrive as validated JSON instead
  of a ``TOOL_CALL: name(k="v")`` line parsed by regex, which broke on any
  argument containing ")" and allowed one call per turn.
* Text is streamed as the model produces it.
* The client sends the recent conversation, so follow-ups ("add a task to that
  project") work. History is plain text; it grants nothing, because every tool
  re-checks the signed-in user's permissions.
* Read tools run immediately. Write tools (``WRITE_TOOL_NAMES``) are not run:
  the stream ends with a ``confirm`` event, and the tool runs only when the user
  approves it, in a follow-up request carrying ``approve``.

Stream events (``data: {"type": ..., ...}``):
``token`` text · ``tool_start``/``tool_end`` a read tool ran · ``confirm`` a write
awaits approval · ``error`` readable message · ``status`` ``done`` (always last).
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from pydantic import BaseModel, Field

from gazzali.models import User
from gazzali.agent_tools import PM_TOOLS, WRITE_TOOL_NAMES, current_user_id

from ..._ai import get_pm_chat_model
from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_TOOL_ROUNDS = 8
_MAX_HISTORY_TURNS = 20
_TOOLS_BY_NAME = {t.name: t for t in PM_TOOLS}

# What the user sees instead of function names.
TOOL_LABELS: dict[str, str] = {
    "pm_create_project": "Create project",
    "pm_list_projects": "Look up your projects",
    "pm_get_project": "Read project details",
    "pm_create_task": "Create task",
    "pm_list_tasks": "Look up tasks",
    "pm_create_experiment": "Create experiment",
    "pm_list_experiments": "Look up experiments",
    "pm_add_experiment_entry": "Add experiment entry",
    "pm_list_experiment_entries": "Read experiment entries",
    "pm_list_publications": "Look up papers",
    "pm_get_publication": "Read paper details",
    "pm_create_publication": "Create paper",
    "pm_create_lab": "Create lab",
    "pm_list_labs": "Look up labs",
    "pm_get_lab": "Read lab details",
    "pm_list_grants": "Look up grants",
    "pm_list_conferences": "Look up conferences",
    "pm_list_irbs": "Look up ethics approvals",
    "pm_global_search": "Search",
}


def _get_model():
    return get_pm_chat_model(temperature=0.3, streaming=True)


def _system_prompt(context: dict | None) -> str:
    ctx = context or {}
    parts = [
        "You are the AI research assistant of a university research-management platform.",
        "Use the tools to look things up instead of guessing ids or facts.",
        "Tools that create things are shown to the user for confirmation before they run,",
        "so call them directly with complete arguments when the user asks for a change.",
        "Never invent results, numbers or citations. Answer concisely, in the user's language.",
    ]
    if ctx.get("project_id"):
        parts.append(f"The user is looking at project {ctx['project_id']}; assume that project unless they name another.")
    if ctx.get("page"):
        parts.append(f"Current page: {ctx['page']}")
    return "\n".join(parts)


def _text_of(content: Any) -> str:
    """Chunk content is a string for most providers, a list of blocks for some."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return ""


def _created_id(result: str) -> str | None:
    m = re.search(r"\bid=([A-Za-z0-9_-]+)", result)
    return m.group(1) if m else None


def result_link(name: str, args: dict, result: str) -> str | None:
    """UI path for what a write tool created, so the user can open it in one click."""
    if result.startswith("Error"):
        return None
    new_id = _created_id(result)
    if name == "pm_create_project" and new_id:
        return f"/projects/{new_id}"
    if name == "pm_create_task" and args.get("project_id"):
        return f"/projects/{args['project_id']}"
    if name == "pm_create_experiment" and new_id and args.get("project_id"):
        return f"/projects/{args['project_id']}/experiments?exp={new_id}"
    if name == "pm_create_publication" and new_id:
        return f"/publications/{new_id}"
    if name == "pm_create_lab" and new_id:
        return f"/labs/{new_id}"
    return None


def _event(kind: str, **data: Any) -> str:
    return f"data: {json.dumps({'type': kind, **data})}\n\n"


async def _call_tool(name: str, args: dict) -> str:
    tool = _TOOLS_BY_NAME.get(name)
    if tool is None:
        return f"Error: unknown tool '{name}'."
    try:
        return str(await tool.ainvoke(args))
    except Exception as exc:  # a tool bug must not end the conversation
        logger.exception("Copilot tool %s failed", name)
        return f"Error: {name} failed ({type(exc).__name__})."


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ApprovedAction(BaseModel):
    name: str
    args: dict[str, Any] = {}


class CopilotRequest(BaseModel):
    message: str = Field(default="", max_length=8000)
    history: list[ChatTurn] = []
    context: dict | None = None
    approve: ApprovedAction | None = None
    session_id: str = ""  # accepted for compatibility; history now travels with the request


def _initial_messages(body: CopilotRequest) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(_system_prompt(body.context))]
    for turn in body.history[-_MAX_HISTORY_TURNS:]:
        messages.append(HumanMessage(turn.content) if turn.role == "user" else AIMessage(turn.content))
    if body.message.strip():
        messages.append(HumanMessage(body.message.strip()))
    return messages


async def _copilot_steps(body: CopilotRequest, user_id: str) -> AsyncGenerator[str, None]:
    token = current_user_id.set(user_id)
    try:
        messages = _initial_messages(body)

        if body.approve is not None:
            name, args = body.approve.name, body.approve.args
            if name not in WRITE_TOOL_NAMES:
                yield _event("error", message="Only actions that change data need approval.")
                return
            # The tool itself re-checks the user's permissions on the project.
            result = await _call_tool(name, args)
            ok = not result.startswith("Error")
            yield _event("tool_end", name=name, label=TOOL_LABELS.get(name, name), ok=ok,
                         summary=result[:300], link=result_link(name, args, result))
            call_id = f"approved-{uuid.uuid4().hex[:8]}"
            messages.append(AIMessage(content="", tool_calls=[{"id": call_id, "name": name, "args": args}]))
            messages.append(ToolMessage(result, tool_call_id=call_id))

        try:
            model = _get_model().bind_tools(PM_TOOLS)
        except NotImplementedError:
            yield _event("error", message="The configured AI model cannot use tools. Choose another model in Settings.")
            return

        for _ in range(_MAX_TOOL_ROUNDS):
            full: Any = None
            async for chunk in model.astream(messages):
                full = chunk if full is None else full + chunk
                if text := _text_of(chunk.content):
                    yield _event("token", data=text)
            if full is None:
                return
            calls = list(getattr(full, "tool_calls", None) or [])
            if not calls:
                return
            messages.append(AIMessage(content=full.content, tool_calls=calls))
            for call in calls:
                name, args = call["name"], call.get("args") or {}
                if name in WRITE_TOOL_NAMES:
                    # Stop here: the user decides. Later calls in this turn are dropped;
                    # the model can repeat them after the approval round-trip.
                    yield _event("confirm", name=name, label=TOOL_LABELS.get(name, name), args=args)
                    return
                yield _event("tool_start", name=name, label=TOOL_LABELS.get(name, name))
                result = await _call_tool(name, args)
                yield _event("tool_end", name=name, label=TOOL_LABELS.get(name, name),
                             ok=not result.startswith("Error"), summary=result[:300], link=None)
                messages.append(ToolMessage(result, tool_call_id=call["id"]))
        yield _event("error", message="Stopped after several tool steps. Try a more specific request.")
    except Exception:
        logger.exception("Copilot failed")
        yield _event("error", message="The assistant ran into a problem. Please try again.")
    finally:
        current_user_id.reset(token)


async def _run_copilot(body: CopilotRequest, user_id: str) -> AsyncGenerator[str, None]:
    """Every stream ends with ``status: done``, including early returns and errors."""
    async for event in _copilot_steps(body, user_id):
        yield event
    yield _event("status", data="done")


@router.post("/copilot/stream")
async def copilot_stream(body: CopilotRequest, user: User = Depends(get_current_user)):
    return StreamingResponse(
        _run_copilot(body, user.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/copilot")
async def copilot_sync(body: CopilotRequest, user: User = Depends(get_current_user)):
    """Non-streaming variant: the same conversation, collected into one reply."""
    text: list[str] = []
    pending: dict | None = None
    async for raw in _run_copilot(body, user.id):
        event = json.loads(raw[len("data: "):])
        if event["type"] == "token":
            text.append(event["data"])
        elif event["type"] == "confirm":
            pending = {"name": event["name"], "args": event["args"]}
        elif event["type"] == "error":
            text.append(f"\n{event['message']}")
    return {"response": "".join(text), "pending_action": pending}
