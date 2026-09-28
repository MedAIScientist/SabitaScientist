"""Agent middleware configuration — inspect and customize the agent middleware chain.

Exposes EvoScientist's middleware components so the PM dashboard can
select which middleware to enable for custom agent configurations.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...models import User
from ..deps import get_current_user

router = APIRouter()


@router.get("/middleware/available")
def list_available_middleware(
    current_user: User = Depends(get_current_user),
):
    """List all available middleware components from EvoScientist.

    Returns the middleware names and descriptions so the PM dashboard
    can offer a middleware configuration UI.
    """
    return {
        "middleware": [
            {
                "name": "ConfigurableModelMiddleware",
                "description": "Model override from config — switch LLM provider/model mid-session.",
                "enabled_by_default": True,
            },
            {
                "name": "ModelFallbackMiddleware",
                "description": "Fallback to alternative models when the primary model fails.",
                "enabled_by_default": True,
            },
            {
                "name": "CodeInterpreterMiddleware",
                "description": "JavaScript code interpreter for data analysis and visualization.",
                "enabled_by_default": True,
            },
            {
                "name": "ToolSelectorMiddleware",
                "description": "Smart tool selection routing based on task type.",
                "enabled_by_default": True,
            },
            {
                "name": "EvoMemoryMiddleware",
                "description": "Cross-session memory — reads/writes observations for agent awareness.",
                "enabled_by_default": True,
            },
            {
                "name": "EvoMemoryLifecycleMiddleware",
                "description": "Manages memory worker lifecycle — launches background workers post-turn.",
                "enabled_by_default": True,
            },
            {
                "name": "BackgroundExecutionMiddleware",
                "description": "run_in_background / check_process / stop_process for long-running tasks.",
                "enabled_by_default": True,
            },
            {
                "name": "AsyncWatcherMiddleware",
                "description": "Async sub-agent lifecycle tracking.",
                "enabled_by_default": True,
            },
            {
                "name": "ContextOverflowMapperMiddleware",
                "description": "Context window management — truncates/compresses when nearing limits.",
                "enabled_by_default": True,
            },
            {
                "name": "ToolErrorHandlerMiddleware",
                "description": "Structured tool error messages instead of raw exceptions.",
                "enabled_by_default": True,
            },
            {
                "name": "AskUserMiddleware",
                "description": "Interrupt-based user questions for human-in-the-loop decisions.",
                "enabled_by_default": True,
            },
            {
                "name": "SchedulerMiddleware",
                "description": "Scheduled task execution via background runner.",
                "enabled_by_default": True,
            },
            {
                "name": "ContextEditingMiddleware",
                "description": "Edits context in place for efficient token usage.",
                "enabled_by_default": True,
            },
            {
                "name": "RuntimeContextMiddleware",
                "description": "Injects runtime metadata (workspace, session info) into the agent context.",
                "enabled_by_default": True,
            },
        ]
    }
