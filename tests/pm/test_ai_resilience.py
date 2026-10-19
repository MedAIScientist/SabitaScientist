"""Provider failures: which ones deserve a retry, and what the user is told.

A retired model and a busy provider need different answers. The first is never
coming back, so the next configured model takes over. The second usually clears in
a moment, so the same model gets one more chance before anything else changes. And
when the provider is at fault, the user should be told that instead of "the
assistant ran into a problem" — which reads like a bug in the assistant.
"""

from __future__ import annotations

import asyncio

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage

from gazzali import _ai

REQ = httpx.Request("POST", "https://provider.test/v1/chat/completions")


def status_error(code: int) -> openai.APIStatusError:
    return openai.APIStatusError("boom", response=httpx.Response(code, request=REQ), body=None)


class TestClassification:
    def test_overload_message_without_a_status_code_is_transient(self) -> None:
        """The streaming API raises a bare APIError, which is what production hit."""
        exc = openai.APIError("Service temporarily overloaded", request=REQ, body=None)
        assert _ai.is_transient(exc) is True

    @pytest.mark.parametrize("code", [408, 425, 429, 500, 502, 503, 504])
    def test_retryable_status_codes_are_transient(self, code: int) -> None:
        assert _ai.is_transient(status_error(code)) is True

    def test_connection_and_timeout_failures_are_transient(self) -> None:
        assert _ai.is_transient(openai.APIConnectionError(request=REQ)) is True

    def test_a_retired_model_is_gone_but_not_transient(self) -> None:
        """Retrying a decommissioned model would just waste the user's time."""
        assert _ai.is_gone(status_error(410)) is True
        assert _ai.is_transient(status_error(410)) is False
        assert _ai.is_gone(status_error(404)) is True

    @pytest.mark.parametrize("code", [400, 401, 403, 422])
    def test_a_request_the_provider_rejects_is_not_retried(self, code: int) -> None:
        assert _ai.is_transient(status_error(code)) is False

    def test_unrelated_exceptions_are_not_transient(self) -> None:
        assert _ai.is_transient(ValueError("nope")) is False


class FakeChat:
    """A model that fails a scripted number of times before answering."""

    def __init__(self, model: str, failures: list[Exception]) -> None:
        self.model_name = model
        # Shared, not copied: a retry builds a new instance, and it must see the
        # failures the previous attempt already consumed.
        self._failures = failures

    async def ainvoke(self, _messages):
        if self._failures:
            raise self._failures.pop(0)
        return AIMessage(content=f"answered by {self.model_name}")


def _wire(monkeypatch, scripts: dict[str, list[Exception]], used: list[str]) -> None:
    monkeypatch.delenv("PM_LLM_MODEL", raising=False)
    monkeypatch.setenv("PM_LLM_FALLBACK_MODELS", "backup/model")
    monkeypatch.setattr(_ai, "RETRY_DELAY_S", 0)

    queues = {name: list(exc_list) for name, exc_list in scripts.items()}

    def factory(**kwargs):
        name = kwargs["model"]
        used.append(name)
        return FakeChat(name, queues.setdefault(name, []))

    monkeypatch.setattr(_ai, "get_pm_chat_model", factory)


class TestDirectPath:
    def test_a_busy_model_is_retried_before_falling_back(self, monkeypatch) -> None:
        """One blip should not cost the user the whole answer, or switch models."""
        used: list[str] = []
        busy = openai.APIError("Service temporarily overloaded", request=REQ, body=None)
        _wire(monkeypatch, {_ai.settings.DEFAULT_LLM_MODEL: [busy]}, used)

        answer = asyncio.run(_ai.run_llm_direct_async("One word.", "Capital?"))

        assert answer == f"answered by {_ai.settings.DEFAULT_LLM_MODEL}"
        assert used == [_ai.settings.DEFAULT_LLM_MODEL, _ai.settings.DEFAULT_LLM_MODEL]

    def test_a_model_that_stays_busy_hands_over_to_the_fallback(self, monkeypatch) -> None:
        used: list[str] = []
        busy = openai.APIError("Service temporarily overloaded", request=REQ, body=None)
        _wire(
            monkeypatch,
            {_ai.settings.DEFAULT_LLM_MODEL: [busy, busy, busy]},
            used,
        )

        answer = asyncio.run(_ai.run_llm_direct_async("One word.", "Capital?"))

        assert answer == "answered by backup/model"
        assert used == [
            _ai.settings.DEFAULT_LLM_MODEL,
            _ai.settings.DEFAULT_LLM_MODEL,
            "backup/model",
        ]

    def test_a_rejected_request_fails_at_once_without_a_retry(self, monkeypatch) -> None:
        """A 400 is our fault, not the provider's: retrying it only hides the bug."""
        used: list[str] = []
        _wire(monkeypatch, {_ai.settings.DEFAULT_LLM_MODEL: [status_error(400)]}, used)

        with pytest.raises(openai.APIStatusError):
            asyncio.run(_ai.run_llm_direct_async("One word.", "Capital?"))

        assert used == [_ai.settings.DEFAULT_LLM_MODEL]

    def test_a_retired_model_does_not_get_a_second_chance(self, monkeypatch) -> None:
        used: list[str] = []
        _wire(monkeypatch, {_ai.settings.DEFAULT_LLM_MODEL: [status_error(410)]}, used)

        answer = asyncio.run(_ai.run_llm_direct_async("One word.", "Capital?"))

        assert answer == "answered by backup/model"
        assert used == [_ai.settings.DEFAULT_LLM_MODEL, "backup/model"]
