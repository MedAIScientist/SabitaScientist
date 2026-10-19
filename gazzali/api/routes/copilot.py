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

import asyncio
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

from gazzali.agent_tools import PM_TOOLS, WRITE_TOOL_NAMES, current_user_id
from gazzali.models import User

from ... import _ai, settings
from ..._ai import get_pm_chat_model, is_gone, is_transient
from ...crud.ai_usage import UsageContext, extract_usage, record_usage_safely
from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# Tool schemas are the bulk of every copilot request: all 19 of them cost roughly
# 3.2k tokens before the user has typed anything. Most are irrelevant to the page the
# user is on, so each turn sends a small core plus that page's own tools. The full
# registry is still used to *run* tools, so an action the user approved earlier keeps
# working even when it is not in the current page's set.
CORE_TOOLS = ("pm_global_search", "pm_list_projects")

PAGE_TOOLS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "/projects",
        (
            "pm_get_project", "pm_list_tasks", "pm_create_task",
            "pm_list_experiments", "pm_create_experiment",
            "pm_list_experiment_entries", "pm_add_experiment_entry",
            "pm_create_publication",
        ),
    ),
    (
        "/publications",
        (
            "pm_list_publications", "pm_get_publication", "pm_create_publication",
            "pm_list_experiments", "pm_list_experiment_entries", "pm_add_experiment_entry",
        ),
    ),
    ("/labs", ("pm_list_labs", "pm_get_lab", "pm_create_lab", "pm_create_project")),
    ("/grants", ("pm_list_grants",)),
    ("/conferences", ("pm_list_conferences",)),
    ("/irb", ("pm_list_irbs",)),
    ("/supervision", ()),
    ("/journey", ()),
    ("/requirements", ()),
    ("/weekly-update", ()),
)

# Anything else (home, admin, people, memory, health…): a browsing set plus the one
# creation an admin most often wants from the landing page.
DEFAULT_TOOLS = (
    "pm_create_project", "pm_list_publications", "pm_list_labs",
    "pm_list_grants", "pm_list_conferences", "pm_list_irbs",
)

_MAX_TOOL_ROUNDS = 8
GENERIC_FAILURE = "The assistant ran into a problem. Please try again."
BUSY_PROVIDER = "The AI provider is temporarily overloaded. Please try again in a moment."
CUT_SHORT = "The reply was cut short because the AI provider dropped the connection. Please try again."

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


def tools_for(context: dict | None) -> list:
    """The tools worth sending for the page the user is on.

    Narrowing the set is a cost decision, so the model is told about it in the system
    prompt: asked for something outside this page, it should point at the right page
    rather than invent a tool or claim success it cannot deliver.
    """
    page = (context or {}).get("page") or ""
    names = set(CORE_TOOLS)
    for prefix, group in PAGE_TOOLS:
        if page.startswith(prefix):
            names.update(group)
            break
    else:
        names.update(DEFAULT_TOOLS)
    return [t for t in PM_TOOLS if t.name in names]


def _system_prompt(context: dict | None) -> str:
    ctx = context or {}
    parts = [
        "You are the AI research assistant of a university research-management platform.",
        "Use the tools to look things up instead of guessing ids or facts.",
        "Tools that create things are shown to the user for confirmation before they run,",
        "so call them directly with complete arguments when the user asks for a change.",
        "Never invent results, numbers or citations. Answer concisely, in the user's language.",
        "Only the tools that fit the current page are available. If the user asks for",
        "something you cannot do here, name the page where it is possible instead of",
        "guessing or claiming it is done.",
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


def _record_round(
    full: Any, model: Any, messages: list[BaseMessage], body: CopilotRequest, user_id: str
) -> None:
    """Account for one streamed round: the copilot spends tokens like any other feature.

    Best-effort by design — a bookkeeping failure must never break a conversation —
    and an estimated row is labelled as an estimate by the accounting layer, so the
    usage panel never presents a guess as a measurement.
    """
    prompt_tokens, completion_tokens, total_tokens = extract_usage(full)
    record_usage_safely(
        context=UsageContext(
            task="copilot",
            user_id=user_id,
            project_id=(body.context or {}).get("project_id"),
        ),
        model=getattr(model, "model_name", None),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        prompt_chars=sum(len(str(m.content or "")) for m in messages),
        output_chars=len(_text_of(getattr(full, "content", ""))),
    )


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

        selected_tools = tools_for(body.context)
        try:
            model = _get_model().bind_tools(selected_tools)
        except NotImplementedError:
            yield _event("error", message="The configured AI model cannot use tools. Choose another model in Settings.")
            return

        fallbacks = settings.llm_models()[1:]
        for _ in range(_MAX_TOOL_ROUNDS):
            full: Any = None
            retried = False
            while True:
                try:
                    async for chunk in model.astream(messages):
                        full = chunk if full is None else full + chunk
                        if text := _text_of(chunk.content):
                            yield _event("token", data=text)
                    break
                except Exception as exc:
                    # Once text has been shown to the user, replaying the round would
                    # duplicate it; say the reply was cut short instead.
                    if full is not None:
                        logger.warning("Copilot stream broke mid-answer: %s", exc)
                        yield _event("error", message=CUT_SHORT)
                        return
                    # A busy provider usually clears in a moment, so the same model
                    # gets one silent second chance before the next one is tried.
                    if is_transient(exc) and not retried:
                        retried = True
                        logger.warning("Copilot model %s is busy (%s); retrying once", model.model_name, exc)
                        await asyncio.sleep(_ai.RETRY_DELAY_S)
                        continue
                    if (is_gone(exc) or is_transient(exc)) and fallbacks:
                        logger.warning("Copilot falling back from %s (%s)", model.model_name, exc)
                        model = get_pm_chat_model(
                            temperature=0.3, streaming=True, model=fallbacks.pop(0)
                        ).bind_tools(selected_tools)
                        retried = False
                        continue
                    raise
            if full is None:
                return
            # One row per round, whether it ends in a tool call or an answer: each
            # round is a separate LLM call and would otherwise be invisible.
            _record_round(full, model, messages, body, user_id)
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
    except Exception as exc:
        logger.exception("Copilot failed")
        # A busy provider is not a bug in the assistant, and saying so lets the user
        # decide whether to wait; anything else keeps the generic wording.
        yield _event(
            "error",
            message=BUSY_PROVIDER if is_transient(exc) else GENERIC_FAILURE,
        )
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
