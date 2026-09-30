"""AI integration: direct access to EvoScientist's LLM, tools, skills, prompts, and memory.

Instead of routing every AI request through the HTTP agent runner, this module
provides a fast path that uses EvoScientist's ``get_chat_model()`` for direct
LLM calls, ``EvoScientist.prompts`` for structured writing guidance,
``EvoScientist.tools`` for research-backed operations, and
``EvoScientist.memory`` for cross-session context.
"""

from __future__ import annotations

import json
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..config.settings import get_effective_config
from ..llm.models import DEFAULT_MODEL, get_chat_model
from ..prompts import REPORT_TEMPLATE, WRITING_GUIDELINES
from .crud.ai_usage import UsageContext, extract_usage, record_usage_safely

# =========================================================================
# Skill Integration
# =========================================================================


def _load_skill_prompt(skill_name: str) -> str:
    """Load a skill's SKILL.md from EvoScientist's skill directories."""
    from ..paths import GLOBAL_SKILLS_DIR, USER_SKILLS_DIR

    for base in (USER_SKILLS_DIR, GLOBAL_SKILLS_DIR):
        skill_dir = base / skill_name
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8")
    return ""


def _build_skill_augmented_system_prompt(
    base_instructions: str, skill_names: list[str]
) -> str:
    """Augment system prompt with relevant skill guidance."""
    parts = [base_instructions]
    for name in skill_names:
        prompt = _load_skill_prompt(name)
        if prompt:
            parts.append(f"\n\n--- {name} skill guidance ---\n{prompt}")
    return "\n\n".join(parts)


# =========================================================================
# Shared LLM setup (extracted to avoid sync/async duplication)
# =========================================================================


def pm_model_choice(model: str | None = None) -> tuple[str, str | None]:
    """The (model, provider) the PM's direct AI calls and the copilot use.

    ``auxiliary_model`` + ``auxiliary_provider`` from the settings (env:
    EVOSCIENTIST_AUXILIARY_MODEL / EVOSCIENTIST_AUXILIARY_PROVIDER). The provider
    matters: one model name can be served by several providers (deepseek-v4-flash
    by DeepSeek and by OpenRouter), and it was previously ignored.
    """
    if model:
        return model, None
    config = get_effective_config()
    if config.auxiliary_model:
        return config.auxiliary_model, config.auxiliary_provider or None
    return DEFAULT_MODEL, None


def _prepare_chat(
    system_prompt: str,
    skill_guidance: list[str] | None = None,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
) -> tuple:
    """Build the augmented system prompt and return (chat, system_prompt)."""
    if skill_guidance:
        system_prompt = _build_skill_augmented_system_prompt(
            system_prompt, skill_guidance
        )
    model_name, provider = pm_model_choice(model)
    chat = get_chat_model(model_name, provider=provider, temperature=temperature, max_tokens=max_tokens)
    return chat, system_prompt


# =========================================================================
# Usage accounting
# =========================================================================


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


# =========================================================================
# Direct LLM Access (via EvoScientist.llm.get_chat_model)
# =========================================================================


def run_llm_direct(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    skill_guidance: list[str] | None = None,
    context: UsageContext | None = None,
) -> str:
    """Run a direct LLM call through EvoScientist's model infrastructure."""
    chat, sp = _prepare_chat(system_prompt, skill_guidance, model, temperature, max_tokens)
    started = time.monotonic()
    result = chat.invoke([SystemMessage(content=sp), HumanMessage(content=user_prompt)])
    _record_call(
        context,
        getattr(chat, "model_name", None) or model or "unknown",
        sp,
        user_prompt,
        result,
        int((time.monotonic() - started) * 1000),
    )
    return str(result.content)


async def run_llm_direct_async(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    skill_guidance: list[str] | None = None,
    context: UsageContext | None = None,
) -> str:
    """Async variant of ``run_llm_direct``."""
    chat, sp = _prepare_chat(system_prompt, skill_guidance, model, temperature, max_tokens)
    started = time.monotonic()
    result = await chat.ainvoke([SystemMessage(content=sp), HumanMessage(content=user_prompt)])
    _record_call(
        context,
        getattr(chat, "model_name", None) or model or "unknown",
        sp,
        user_prompt,
        result,
        int((time.monotonic() - started) * 1000),
    )
    return str(result.content)


# =========================================================================
# Structured Output (JSON)
# =========================================================================


def generate_json_direct(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.1,
    skill_guidance: list[str] | None = None,
    context: UsageContext | None = None,
) -> dict[str, Any]:
    """Run a direct LLM call requesting JSON output.

    Raises:
        json.JSONDecodeError: If the model output is not valid JSON.
    """
    if skill_guidance:
        system_prompt = _build_skill_augmented_system_prompt(
            system_prompt, skill_guidance
        )

    config = get_effective_config()
    model_name = model or config.auxiliary_model or DEFAULT_MODEL

    chat = get_chat_model(model_name, temperature=temperature)

    started = time.monotonic()
    result = chat.invoke([
        SystemMessage(content=system_prompt + "\n\nRespond with valid JSON only."),
        HumanMessage(content=user_prompt),
    ])
    _record_call(
        context,
        getattr(chat, "model_name", None) or model_name,
        system_prompt,
        user_prompt,
        result,
        int((time.monotonic() - started) * 1000),
    )
    return json.loads(str(result.content))


# =========================================================================
# Drafting Helpers (using EvoScientist.prompts for writing guidance)
# =========================================================================


def build_writing_system_prompt(task_specific_instructions: str) -> str:
    """Build a writing system prompt that includes EvoScientist's writing guidelines.

    Uses ``WRITING_GUIDELINES`` and ``REPORT_TEMPLATE`` from
    ``EvoScientist.prompts`` to ensure AI-generated content follows the
    same style rules as the main agent.
    """
    return f"""{task_specific_instructions}

{WRITING_GUIDELINES}

{REPORT_TEMPLATE}"""


# =========================================================================
# Research Tools (using EvoScientist.tools)
# =========================================================================


async def search_and_summarize(query: str, max_results: int = 5) -> str:
    """Search the web using EvoScientist's ``tavily_search`` tool and return results.

    Uses the same Tavily client that the main research agent uses, configured
    via EvoScientist's settings (requires ``TAVILY_API_KEY``).
    """
    from ..tools.search import tavily_search

    return await tavily_search.ainvoke({"query": query, "max_results": max_results})


async def think_about(topic: str) -> str:
    """Use EvoScientist's ``think_tool`` for structured reasoning.

    This enables the PM AI endpoints to use the same reflection pattern
    that the main agent uses for decision-making.
    """
    from ..tools.think import think_tool

    return await think_tool.ainvoke({"reflection": topic})


# =========================================================================
# Memory Integration
# =========================================================================


def record_pm_observation(
    memory_dir: str,
    project_id: str,
    source_agent: str,
    summary: str,
    observation: str,
    session_id: str = "pm_dashboard",
) -> None:
    """Record an observation via EvoScientist.memory so the main agent can find it.

    This bridges PM data (project context, experiment results, publication
    drafts) into the agent's cross-session memory.

    Args:
        memory_dir: Memory directory path.
        project_id: PM project ID.
        source_agent: Agent name that created this observation.
        summary: Short summary/title of the observation.
        observation: Main body text.
        session_id: Source session identifier.
    """
    from ..memory.observations.store import record_observation_file
    from ..memory.types import MemoryScope, MemorySourceType, MemoryType

    record_observation_file(
        memory_dir=memory_dir,
        project_id=project_id,
        memory_type=MemoryType.SEMANTIC,
        summary=summary,
        observation=observation[:3000],
        why_it_matters="Recorded via PM dashboard.",
        scope=MemoryScope.PROJECT,
        source_type=MemorySourceType.TURN,
        source_session_id=session_id,
        source_agent=source_agent,
    )


def list_available_skills() -> list[str]:
    """List EvoScientist skill names available for use in PM AI endpoints."""
    from ..paths import GLOBAL_SKILLS_DIR, USER_SKILLS_DIR

    skills: list[str] = []
    for base in (USER_SKILLS_DIR, GLOBAL_SKILLS_DIR):
        if base.exists():
            for entry in base.iterdir():
                if entry.is_dir() and (entry / "SKILL.md").exists():
                    skills.append(entry.name)
    return sorted(set(skills))


# =========================================================================
# Project Knowledge Retrieval (via EvoScientist.memory.search)
# =========================================================================


def search_project_knowledge(
    project_id: str,
    query: str,
    memory_dir: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Search EvoScientist memory for observations related to a project.

    Uses ``search_observation_files()`` from ``EvoScientist.memory`` to
    retrieve past agent observations about a project. This enables PM's
    AI drafting features to reference prior work automatically.

    Args:
        project_id: The PM project ID to search within.
        query: Natural language search query.
        memory_dir: Optional memory directory override (defaults to
                    ``MEMORIES_DIR``).
        limit: Maximum results.

    Returns:
        List of observation documents with id, summary, body, score.
    """
    from ..memory.observations.store import search_observation_files
    from ..memory.types import ObservationSearchMode
    from ..paths import MEMORIES_DIR

    mem_dir = memory_dir or str(MEMORIES_DIR)
    results = search_observation_files(
        memory_dir=mem_dir,
        project_id=project_id,
        query=query,
        limit=limit,
        mode=ObservationSearchMode.RANKED,
    )
    return [
        {
            "id": r.get("id", ""),
            "title": r.get("summary", "") or r.get("title", ""),
            "body": (r.get("body", "") or "")[:500],
            "score": r.get("score", 0.0),
        }
        for r in results
    ]


def build_project_knowledge_context(
    project_id: str,
    query: str | None = None,
    memory_dir: str | None = None,
    max_observations: int = 5,
) -> str:
    """Build a context string from project memory for AI drafting prompts.

    Uses ``build_observation_index_context()`` from EvoScientist.memory to
    create a structured summary of project knowledge that can be injected into
    drafting prompts.

    Args:
        project_id: PM project ID.
        query: Optional search query to focus context on a topic.
        memory_dir: Optional memory directory override.
        max_observations: Maximum observations to include.

    Returns:
        Formatted context string ready for prompt injection.
    """
    from ..memory.observations.index import build_observation_index_context
    from ..paths import MEMORIES_DIR

    mem_dir = memory_dir or str(MEMORIES_DIR)
    context = build_observation_index_context(
        memory_dir=mem_dir,
        project_id=project_id,
        max_inline_chars=max_observations * 800,
    )
    if not context:
        return ""

    return f"""Previous project observations:

{context}"""
