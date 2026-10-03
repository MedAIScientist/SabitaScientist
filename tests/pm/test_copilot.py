"""Copilot: native tool calls, streamed text, history, and confirmation before writes."""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from gazzali.api.routes import copilot


class ScriptedModel(BaseChatModel):
    """Replies with a fixed script: each item is text, or a (tool_name, args) call."""

    script: list[Any]
    seen: list[list[Any]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _next(self, messages):
        self.seen.append(list(messages))
        return self.script.pop(0)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        item = self._next(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=item if isinstance(item, str) else ""))])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        item = self._next(messages)
        if isinstance(item, str):
            for word in item.split(" "):  # several chunks, like a real stream
                yield ChatGenerationChunk(message=AIMessageChunk(content=word + " "))
            return
        name, args = item
        yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=[
            {"name": name, "args": json.dumps(args), "id": f"call-{name}", "index": 0},
        ]))


@pytest.fixture
def model(monkeypatch):
    m = ScriptedModel(script=[], seen=[])
    monkeypatch.setattr(copilot, "_get_model", lambda: m)
    return m


def _events(client, token, **body) -> list[dict]:
    resp = client.post("/api/v1/copilot/stream", json=body, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    return [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]


def _text(events) -> str:
    return "".join(e["data"] for e in events if e["type"] == "token")


def test_plain_answer_streams_in_chunks_and_ends_with_done(client, admin_token, model) -> None:
    model.script = ["Hello there, researcher."]
    events = _events(client, admin_token, message="hi")
    assert sum(e["type"] == "token" for e in events) > 1  # streamed, not one blob
    assert _text(events).strip() == "Hello there, researcher."
    assert events[-1] == {"type": "status", "data": "done"}


def test_read_tool_runs_and_answer_uses_its_result(client, admin_token, model) -> None:
    model.script = [("pm_list_projects", {}), "You have no projects yet."]
    events = _events(client, admin_token, message="what are my projects?")
    kinds = [e["type"] for e in events]
    assert kinds.index("tool_start") < kinds.index("tool_end") < kinds.index("token")
    end = next(e for e in events if e["type"] == "tool_end")
    assert end["label"] == "Look up your projects" and end["ok"] is True
    # The tool result went back to the model as a ToolMessage.
    assert "No projects found." in model.seen[1][-1].content


def test_write_tool_waits_for_confirmation_then_runs(client, admin_token, model) -> None:
    h = {"Authorization": f"Bearer {admin_token}"}
    model.script = [("pm_create_project", {"name": "OCT study"})]
    events = _events(client, admin_token, message="create a project called OCT study")
    confirm = next(e for e in events if e["type"] == "confirm")
    assert confirm["label"] == "Create project" and confirm["args"] == {"name": "OCT study"}
    assert client.get("/api/v1/projects", headers=h).json() == []  # nothing created yet

    model.script = ["Done — your project is ready."]
    events = _events(client, admin_token, approve={"name": "pm_create_project", "args": {"name": "OCT study"}},
                     history=[{"role": "user", "content": "create a project called OCT study"}])
    end = next(e for e in events if e["type"] == "tool_end")
    projects = client.get("/api/v1/projects", headers=h).json()
    assert [p["name"] for p in projects] == ["OCT study"]
    assert end["ok"] and end["link"] == f"/projects/{projects[0]['id']}"
    assert "ready" in _text(events)


def test_approval_cannot_be_used_to_run_arbitrary_tools(client, admin_token, model) -> None:
    events = _events(client, admin_token, approve={"name": "pm_list_grants", "args": {}})
    assert any(e["type"] == "error" for e in events)
    assert not any(e["type"] == "tool_end" for e in events)


def test_history_reaches_the_model(client, admin_token, model) -> None:
    model.script = ["It is called OCT study."]
    _events(client, admin_token, message="what was it called?", history=[
        {"role": "user", "content": "create a project called OCT study"},
        {"role": "assistant", "content": "Created it."},
    ])
    contents = [m.content for m in model.seen[0]]
    assert "create a project called OCT study" in contents and "Created it." in contents


def test_arguments_with_parentheses_survive(client, admin_token, model) -> None:
    """The old regex parser cut arguments at the first ')'."""
    name = "Pilot (phase 1) study"
    model.script = [("pm_create_project", {"name": name})]
    confirm = next(e for e in _events(client, admin_token, message="x") if e["type"] == "confirm")
    assert confirm["args"]["name"] == name


def test_link_for_created_entities() -> None:
    assert copilot.result_link("pm_create_task", {"project_id": "p1"}, "Created task 'x' with id=t1") == "/projects/p1"
    assert copilot.result_link("pm_create_experiment", {"project_id": "p1"}, "Created experiment 'e' with id=e9") \
        == "/projects/p1/experiments?exp=e9"
    assert copilot.result_link("pm_create_task", {"project_id": "p1"}, "Error: nope") is None


def test_model_choice_follows_the_environment(monkeypatch) -> None:
    """Groq + the default model unless PM_LLM_* point somewhere else."""
    from gazzali import _ai, settings

    for key in ("PM_LLM_MODEL", "PM_LLM_BASE_URL", "PM_LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert _ai.pm_model_choice() == (settings.DEFAULT_LLM_MODEL, "api.groq.com")

    monkeypatch.setenv("PM_LLM_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("PM_LLM_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("PM_LLM_API_KEY", "k")
    assert _ai.pm_model_choice() == ("deepseek-v4-flash", "api.deepseek.com")
    chat = _ai.get_pm_chat_model()
    assert chat.model_name == "deepseek-v4-flash"
    assert str(chat.openai_api_base).startswith("https://api.deepseek.com")
