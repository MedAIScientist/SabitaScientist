"""Tests for the runner's streaming contract and its AI usage reporting.

The runner streams from Groq's OpenAI-compatible API. Two things about that stream
have already broken production once: the model name can be decommissioned under us,
and the usage-only final chunk carries no `choices`, which the original parser
indexed blindly.
"""

from __future__ import annotations

import json

from EvoScientist.pm.runner.agent_runner import (
    DEFAULT_RUNNER_MODEL,
    parse_stream_chunk,
)


def test_content_chunk_yields_text() -> None:
    raw = json.dumps({"choices": [{"delta": {"content": "hello"}}]})
    assert parse_stream_chunk(raw) == ("hello", None)


def test_usage_only_chunk_does_not_raise() -> None:
    """This is the chunk shape that used to end the run with an IndexError."""
    usage = {"prompt_tokens": 78, "completion_tokens": 16, "total_tokens": 94}
    raw = json.dumps({"choices": [], "usage": usage})
    assert parse_stream_chunk(raw) == ("", usage)


def test_missing_choices_entirely_is_tolerated() -> None:
    raw = json.dumps({"usage": {"total_tokens": 3}})
    assert parse_stream_chunk(raw) == ("", {"total_tokens": 3})


def test_delta_without_content_yields_no_text() -> None:
    """Reasoning models emit deltas that carry no user-visible content."""
    raw = json.dumps({"choices": [{"delta": {"reasoning": "thinking"}}]})
    assert parse_stream_chunk(raw) == ("", None)


def test_malformed_payload_is_skipped_not_raised() -> None:
    assert parse_stream_chunk("not json at all") == ("", None)


def test_default_model_is_not_a_decommissioned_one() -> None:
    """Guard the specific regression: the shipped default was decommissioned by Groq,
    which made every runner-backed AI feature fail silently in production."""
    assert DEFAULT_RUNNER_MODEL != "mixtral-8x7b-32768"
    assert "/" in DEFAULT_RUNNER_MODEL, "Groq model ids are namespaced, e.g. openai/gpt-oss-120b"


def test_configured_model_overrides_the_default(monkeypatch) -> None:
    from EvoScientist.pm.runner import agent_runner

    monkeypatch.setenv("PM_RUNNER_MODEL", "some/other-model")
    assert agent_runner._get_model() == "some/other-model"


def test_model_falls_back_to_the_default_when_unset(monkeypatch) -> None:
    from EvoScientist.pm.runner import agent_runner

    monkeypatch.delenv("PM_RUNNER_MODEL", raising=False)
    assert agent_runner._get_model() == DEFAULT_RUNNER_MODEL
