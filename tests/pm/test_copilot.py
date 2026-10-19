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
    #: Tool names the copilot offered this model, so selection can be asserted.
    offered_tools: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        self.offered_tools = [t.name for t in tools]
        return self

    def _next(self, messages):
        self.seen.append(list(messages))
        return self.script.pop(0)

    #: Set to a dict to make the fake report token usage like a real provider.
    usage_metadata: dict | None = None

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        item = self._next(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=item if isinstance(item, str) else ""))])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        item = self._next(messages)
        usage = self.usage_metadata
        if isinstance(item, str):
            words = item.split(" ")
            for i, word in enumerate(words):  # several chunks, like a real stream
                # Providers attach usage to the last chunk of a stream.
                last = i == len(words) - 1
                yield ChatGenerationChunk(message=AIMessageChunk(
                    content=word + " ", usage_metadata=usage if last else None))
            return
        name, args = item
        yield ChatGenerationChunk(message=AIMessageChunk(
            content="", usage_metadata=usage,
            tool_call_chunks=[
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
    """NVIDIA + the default model unless PM_LLM_* point somewhere else."""
    from gazzali import _ai, settings

    for key in ("PM_LLM_MODEL", "PM_LLM_BASE_URL", "PM_LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert _ai.pm_model_choice() == (settings.DEFAULT_LLM_MODEL, "integrate.api.nvidia.com")

    monkeypatch.setenv("PM_LLM_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("PM_LLM_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("PM_LLM_API_KEY", "k")
    assert _ai.pm_model_choice() == ("deepseek-v4-flash", "api.deepseek.com")
    chat = _ai.get_pm_chat_model()
    assert chat.model_name == "deepseek-v4-flash"
    assert str(chat.openai_api_base).startswith("https://api.deepseek.com")


def test_retired_model_falls_back_to_the_next(monkeypatch) -> None:
    """Providers retire models without warning (NVIDIA, 2026-10-03): a 410 must not break AI."""
    import asyncio

    import httpx
    import openai

    from gazzali import _ai

    monkeypatch.delenv("PM_LLM_MODEL", raising=False)
    monkeypatch.setenv("PM_LLM_FALLBACK_MODELS", "backup/model")
    used: list[str] = []

    class FakeChat:
        def __init__(self, model):
            self.model_name = model

        async def ainvoke(self, messages):
            used.append(self.model_name)
            if self.model_name != "backup/model":
                resp = httpx.Response(410, request=httpx.Request("POST", "https://x"))
                raise openai.APIStatusError("gone", response=resp, body=None)
            return AIMessage(content="Ankara")

    monkeypatch.setattr(_ai, "get_pm_chat_model", lambda **kw: FakeChat(kw["model"]))
    assert asyncio.run(_ai.run_llm_direct_async("One word.", "Capital?")) == "Ankara"
    assert used == [_ai.settings.DEFAULT_LLM_MODEL, "backup/model"]


# ── Provider trouble: retry, hand over, and say what actually happened ────────
#
# Live failure, 2026-10-03: the provider answered a copilot turn with
# "Service temporarily overloaded" and the user saw "The assistant ran into a
# problem" — which reads like a bug in the assistant and offered no way forward.


class FlakyModel:
    """Streams a sentence, but fails a scripted number of times first."""

    def __init__(self, failures: list[Exception], text: str = "Ankara is the capital") -> None:
        self.model_name = "flaky/model"
        self._failures = list(failures)
        self._text = text
        self.calls = 0

    def bind_tools(self, tools, **kwargs):
        return self

    async def astream(self, _messages):
        self.calls += 1
        if self._failures:
            raise self._failures.pop(0)
        for word in self._text.split(" "):
            yield AIMessageChunk(content=word + " ")


def _overloaded() -> Exception:
    import httpx
    import openai

    return openai.APIError(
        "Service temporarily overloaded",
        request=httpx.Request("POST", "https://provider.test/v1/chat/completions"),
        body=None,
    )


def _wire_flaky(monkeypatch, model: FlakyModel) -> None:
    from gazzali import _ai

    monkeypatch.setattr(_ai, "RETRY_DELAY_S", 0)  # no real waiting in tests
    monkeypatch.setattr(copilot, "_get_model", lambda: model)


def test_a_busy_provider_is_retried_instead_of_reported(client, admin_token, monkeypatch) -> None:
    model = FlakyModel([_overloaded()])
    _wire_flaky(monkeypatch, model)

    events = _events(client, admin_token, message="Capital of Turkey?")

    assert [e for e in events if e["type"] == "error"] == []
    assert "".join(e["data"] for e in events if e["type"] == "token").strip() == "Ankara is the capital"
    assert model.calls == 2, "the busy provider was not retried"
    assert events[-1] == {"type": "status", "data": "done"}


def test_a_provider_that_stays_busy_is_described_truthfully(client, admin_token, monkeypatch) -> None:
    from gazzali import _ai

    # Fails the first try, the retry, and every configured fallback model.
    model = FlakyModel([_overloaded() for _ in range(6)])
    monkeypatch.setattr(_ai, "RETRY_DELAY_S", 0)
    monkeypatch.setattr(copilot, "_get_model", lambda: model)
    monkeypatch.setattr(copilot, "get_pm_chat_model", lambda **kwargs: model)

    events = _events(client, admin_token, message="Capital of Turkey?")

    errors = [e["message"] for e in events if e["type"] == "error"]
    assert errors == [copilot.BUSY_PROVIDER]
    assert "ran into a problem" not in errors[0], "a busy provider is not a bug in the assistant"


def test_a_reply_cut_short_is_not_restarted(client, admin_token, monkeypatch) -> None:
    """Replaying a half-delivered answer would show the user the same text twice."""
    model = FlakyModel([], text="Ankara")
    _wire_flaky(monkeypatch, model)

    original = model.astream

    async def cut_off(messages):
        yielded = False
        async for chunk in original(messages):
            yield chunk
            if not yielded:
                yielded = True
                raise _overloaded()

    model.astream = cut_off  # type: ignore[method-assign]

    events = _events(client, admin_token, message="Capital of Turkey?")

    tokens = "".join(e["data"] for e in events if e["type"] == "token")
    assert tokens.strip() == "Ankara"
    assert [e["message"] for e in events if e["type"] == "error"] == [copilot.CUT_SHORT]
    assert model.calls == 1, "the round was replayed after text had already been shown"


# ── Accounting: the copilot spends tokens like every other AI feature ─────────
#
# It streams through ChatOpenAI directly, so it did not pass through the recording
# helper the drafting endpoints use and was invisible in the AI usage panel.


def _usage_rows(db, task: str = "copilot") -> list[dict]:
    import sqlite3

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT task, model, prompt_tokens, completion_tokens, total_tokens, "
            "token_source, user_id, project_id FROM ai_usage WHERE task = ?",
            (task,),
        )
    ]
    conn.close()
    return rows


def test_a_copilot_turn_is_recorded_with_provider_tokens(
    client, admin_token, model, tmp_db, admin_user
) -> None:
    """The provider reported the counts: they must be stored, and attributed."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "OCT study"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["id"]
    model.script = ["Ankara"]
    model.usage_metadata = {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}

    _events(client, admin_token, message="Capital of Turkey?",
            context={"project_id": project_id, "page": "/home"})

    rows = _usage_rows(tmp_db)
    assert len(rows) == 1
    assert rows[0]["total_tokens"] == 150
    assert rows[0]["token_source"] == "provider"
    assert rows[0]["user_id"] == admin_user.id
    assert rows[0]["project_id"] == project_id


def test_a_stale_project_reference_still_records_the_call(
    client, admin_token, model, tmp_db
) -> None:
    """The context comes from the browser, so it can name a project that is gone.

    Losing the row would make the call invisible; the reference is dropped instead.
    """
    model.script = ["Ankara"]
    model.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

    _events(client, admin_token, message="Capital of Turkey?",
            context={"project_id": "no-such-project", "page": "/home"})

    rows = _usage_rows(tmp_db)
    assert len(rows) == 1
    assert rows[0]["project_id"] is None
    assert rows[0]["total_tokens"] == 15


def test_a_silent_provider_is_recorded_as_an_estimate(client, admin_token, model, tmp_db) -> None:
    """Better an honest approximate row than an invisible call."""
    model.script = ["Ankara is the capital of Turkey"]
    model.usage_metadata = None  # provider said nothing

    _events(client, admin_token, message="Capital of Turkey?")

    rows = _usage_rows(tmp_db)
    assert len(rows) == 1
    assert rows[0]["token_source"] == "estimated"
    assert rows[0]["total_tokens"] > 0


def test_each_tool_round_is_its_own_recorded_call(client, admin_token, model, tmp_db) -> None:
    """A tool round and the answer round are two LLM calls, so they get two rows."""
    model.script = [("pm_list_projects", {}), "You have no projects yet."]
    model.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

    _events(client, admin_token, message="which projects do I have?")

    rows = _usage_rows(tmp_db)
    assert len(rows) == 2, "a tool round was not accounted for"
    assert {r["total_tokens"] for r in rows} == {15}


# ── Tool selection: the schemas are the bulk of every request ─────────────────
#
# All 19 tool schemas cost ~3.2k tokens before the user types anything, and most are
# irrelevant to the page they are on. Selection is therefore a cost decision that
# must not quietly become a capability loss — the full registry still runs tools.


def test_the_tools_sent_follow_the_page() -> None:
    from gazzali.api.routes.copilot import tools_for

    names = lambda page: {t.name for t in tools_for({"page": page})}  # noqa: E731

    project_page = names("/projects/abc123")
    assert "pm_create_task" in project_page
    assert "pm_add_experiment_entry" in project_page
    # A grants page has no business sending task-creation schemas.
    assert "pm_create_task" not in names("/grants")
    assert "pm_list_grants" in names("/grants")
    # The core is always there, so anything can be looked up by name.
    for page in ("/projects/x", "/grants", "/labs", "/home", "/weekly-update"):
        assert {"pm_global_search", "pm_list_projects"} <= names(page)


def test_an_unknown_page_falls_back_to_the_browsing_set() -> None:
    from gazzali.api.routes.copilot import tools_for

    plain = {t.name for t in tools_for(None)}
    assert plain == {t.name for t in tools_for({"page": "/something-new"})}
    assert "pm_create_project" in plain


def test_the_page_payload_is_much_smaller_than_every_tool() -> None:
    """The saving is the point of the exercise, so it is asserted, not assumed."""
    import json

    from gazzali.agent_tools import PM_TOOLS
    from gazzali.api.routes.copilot import tools_for

    def tokens(tools) -> int:
        total = 0
        for tool in tools:
            schema = tool.args_schema.model_json_schema() if tool.args_schema else {}
            total += len(json.dumps({
                "name": tool.name, "description": tool.description or "", "parameters": schema,
            })) // 4
        return total

    full = tokens(PM_TOOLS)
    for page, ceiling in (("/projects/abc", 0.6), ("/home", 0.7), ("/grants", 0.3)):
        assert tokens(tools_for({"page": page})) < full * ceiling


def test_the_model_is_only_offered_the_pages_tools(client, admin_token, model) -> None:
    model.script = ["Nothing to do."]
    _events(client, admin_token, message="hi", context={"page": "/grants"})

    offered = model.offered_tools
    assert "pm_list_grants" in offered
    assert "pm_create_task" not in offered
    assert len(offered) < len(copilot.PM_TOOLS)


def test_an_approved_action_still_runs_when_its_tool_is_off_this_page(
    client, admin_token, model, tmp_db
) -> None:
    """Selection narrows what is *offered*; it must not break what was already agreed."""
    model.script = ["Created."]
    events = _events(
        client, admin_token,
        approve={"name": "pm_create_lab", "args": {"name": "Vision Lab"}},
        context={"page": "/grants"},
    )

    ends = [e for e in events if e["type"] == "tool_end"]
    assert len(ends) == 1
    assert "unknown tool" not in ends[0]["summary"], ends[0]["summary"]
    labs = client.get("/api/v1/labs", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert [lab["name"] for lab in labs] == ["Vision Lab"]
