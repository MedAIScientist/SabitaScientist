"""Direct LLM access for the PM's AI endpoints and the copilot.

One OpenAI-compatible endpoint (NVIDIA by default, see ``settings.get_llm_config``)
serves every direct call. Skill guidance is read from SKILL.md files in the
skills directories, when a caller asks for it.
"""

from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urlparse

import openai
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from . import settings
from .crud.ai_usage import UsageContext, extract_usage, record_usage_safely

logger = logging.getLogger(__name__)


def _load_skill_prompt(skill_name: str) -> str:
    """Return a skill's SKILL.md text, or "" when it is not installed."""
    for base in (settings.USER_SKILLS_DIR, settings.GLOBAL_SKILLS_DIR):
        skill_file = base / skill_name / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8")
    return ""


def _with_skill_guidance(base_instructions: str, skill_names: list[str]) -> str:
    parts = [base_instructions]
    for name in skill_names:
        prompt = _load_skill_prompt(name)
        if prompt:
            parts.append(f"\n\n--- {name} skill guidance ---\n{prompt}")
    return "\n\n".join(parts)


def pm_model_choice() -> tuple[str, str]:
    """The (model, endpoint host) the PM's direct AI calls and the copilot use."""
    cfg = settings.get_llm_config()
    return cfg["model"], urlparse(cfg["base_url"]).hostname or cfg["base_url"]


def get_pm_chat_model(
    temperature: float = 0.3,
    max_tokens: int | None = None,
    streaming: bool = False,
    model: str | None = None,
) -> ChatOpenAI:
    """A chat model on the configured OpenAI-compatible endpoint."""
    cfg = settings.get_llm_config()
    return ChatOpenAI(
        model=model or cfg["model"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"] or "missing-api-key",
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        stream_usage=True,
    )


def _record_call(
    context: UsageContext | None,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    result: object,
    duration_ms: int,
) -> None:
    """Record one direct LLM call. Never raises: accounting must not break drafting.

    When the provider reports usage we store the real counts; otherwise the
    accounting layer derives an estimate and labels it as one.
    """
    if context is None:
        return
    prompt_tokens, completion_tokens, total_tokens = extract_usage(result)
    output_text = str(getattr(result, "content", "") or "")
    record_usage_safely(
        context=context,
        model=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        prompt_chars=len(system_prompt) + len(user_prompt),
        output_chars=len(output_text),
        duration_ms=duration_ms,
    )


# The model was retired or renamed by the provider: try the next configured one.
GONE = (404, 410)

# The provider is momentarily unavailable: overloaded, rate-limited, or a 5xx.
# These clear on their own, so they deserve a retry instead of an apology.
TRANSIENT = (408, 409, 425, 429, 500, 502, 503, 504)
RETRY_DELAY_S = 1.5


def is_gone(exc: Exception) -> bool:
    return isinstance(exc, openai.APIStatusError) and exc.status_code in GONE


def is_transient(exc: Exception) -> bool:
    """True when waiting a moment and asking again is likely to work.

    The provider reports overload in more than one shape: a streaming call raises a
    bare ``APIError`` whose message carries the reason and no status code at all,
    while an ordinary call raises ``APIStatusError`` with one. To a user these mean
    the same thing, so both are recognised.
    """
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
        return True
    if isinstance(exc, openai.APIStatusError) and exc.status_code in TRANSIENT:
        return True
    if isinstance(exc, openai.APIError):
        message = str(exc).lower()
        return any(
            phrase in message
            for phrase in ("overload", "temporarily", "rate limit", "try again")
        )
    return False


async def _invoke_with_fallbacks(
    messages: list, *, temperature: float, max_tokens: int | None, models: list[str]
) -> tuple[object, str, int]:
    """Answer from the first model that can, returning (result, model, elapsed_ms).

    The two failure kinds are treated differently because they are different: a
    retired model (404/410) is never coming back, while a busy provider usually
    clears within a second. So a busy model gets one quick second chance, and only
    then does the next configured model take over.
    """
    last: Exception | None = None
    for index, name in enumerate(models):
        for attempt in (1, 2):
            chat = get_pm_chat_model(
                temperature=temperature, max_tokens=max_tokens, model=name
            )
            started = time.monotonic()
            try:
                result = await chat.ainvoke(messages)
            except Exception as exc:
                last = exc
                if is_transient(exc) and attempt == 1:
                    logger.warning("model %s is busy (%s); retrying once", name, exc)
                    await asyncio.sleep(RETRY_DELAY_S)
                    continue
                if (is_gone(exc) or is_transient(exc)) and index < len(models) - 1:
                    logger.warning(
                        "model %s failed (%s); falling back to %s",
                        name,
                        exc,
                        models[index + 1],
                    )
                    break
                raise
            return result, chat.model_name, int((time.monotonic() - started) * 1000)
    raise last if last is not None else RuntimeError("no AI model is configured")


async def run_llm_direct_async(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    skill_guidance: list[str] | None = None,
    context: UsageContext | None = None,
) -> str:
    """Run one system+user prompt and return the text answer."""
    if skill_guidance:
        system_prompt = _with_skill_guidance(system_prompt, skill_guidance)
    models = [model] if model else settings.llm_models()
    result, model_name, elapsed_ms = await _invoke_with_fallbacks(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        temperature=temperature,
        max_tokens=max_tokens,
        models=models,
    )
    _record_call(context, model_name, system_prompt, user_prompt, result, elapsed_ms)
    return str(result.content)


# Multi-agent debate (paper arXiv:2605.20025 §3.2): one model arguing with itself from
# complementary roles surfaces weak assumptions a single answer tends to confirm.
HYPOTHESIS_ROLES = {
    "Innovator": "Propose bold, high-risk hypotheses that challenge conventional assumptions.",
    "Pragmatist": "Judge feasibility with the data, compute and time actually available; keep what can be tested.",
    "Contrarian": "Look for weaknesses, confounds and reasons each idea could be wrong or trivial.",
}
REVIEW_ROLES = {
    "Optimist": "Identify the strongest, best-supported findings and contributions.",
    "Skeptic": "Challenge statistical significance, flag confounds and claims the evidence does not support.",
    "Methodologist": "Evaluate reproducibility, data leakage, baselines and reporting completeness.",
}


async def debate(
    task: str,
    roles: dict[str, str],
    synthesis_instruction: str,
    context: UsageContext | None = None,
) -> str:
    """K role answers in parallel, then a synthesizer; returns Markdown with all parts."""
    names = list(roles)
    answers = await asyncio.gather(*(
        run_llm_direct_async(f"You are the {n}. {roles[n]} Be specific and concise.", task, context=context)
        for n in names
    ))
    panel = "\n\n".join(f"### {n}\n{a.strip()}" for n, a in zip(names, answers, strict=True))
    synthesis = await run_llm_direct_async(
        f"You synthesize a debate between {', '.join(names)}. {synthesis_instruction} "
        "Never invent results, numbers or citations.",
        f"Task:\n{task}\n\nDebate:\n{panel}",
        context=context,
    )
    return f"## Synthesis\n\n{synthesis.strip()}\n\n## Debate\n\n{panel}\n"
