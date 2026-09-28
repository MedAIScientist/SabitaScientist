"""Model selection, system prompt viewer, and cron schedule management.

Integrates EvoScientist's ``set_chat_model()``, ``SYSTEM_PROMPT``, ``llm.models``,
and ``cron.schedule`` so the PM dashboard can switch models, inspect the
active system prompt, and manage recurring agent tasks.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...models import User
from ..deps import get_current_user

router = APIRouter()


# =============================================================================
# Model Selection (via EvoScientist.EvoScientist.set_chat_model)
# =============================================================================


@router.get("/models")
def list_models(current_user: User = Depends(get_current_user)):
    """List all available LLM models from EvoScientist's model registry.

    Returns models grouped by provider with short names and full model IDs.
    Uses ``list_models()`` from ``EvoScientist.llm.models``.
    """
    from ....llm.models import DEFAULT_MODEL, MODELS

    providers: dict[str, list[dict]] = {}
    for short_name, (model_id, provider) in sorted(MODELS.items(), key=lambda x: x[0]):
        providers.setdefault(provider, []).append(
            {"short_name": short_name, "model_id": model_id}
        )

    return {
        "providers": [{"name": p, "models": models} for p, models in providers.items()],
        "default_model": DEFAULT_MODEL,
    }


@router.get("/models/current")
def current_model(current_user: User = Depends(get_current_user)):
    """Return the currently active model (if any) and the default."""
    from ....EvoScientist import _chat_model_key
    from ....llm.models import DEFAULT_MODEL

    model_name = None
    provider = None
    if _chat_model_key:
        model_name, provider = _chat_model_key
    return {
        "current_model": model_name,
        "current_provider": provider,
        "default_model": DEFAULT_MODEL,
    }


@router.post("/models/select")
def select_model(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Switch the active LLM model mid-session.

    Calls ``set_chat_model()`` from EvoScientist.EvoScientist. The model
    change takes effect immediately for subsequent agent runs.
    """
    from ....EvoScientist import set_chat_model
    from ....llm.models import MODELS

    model = body.get("model", "").strip()
    provider = body.get("provider")

    if not model:
        raise HTTPException(status_code=400, detail="model is required")

    if model not in MODELS and provider is None:
        # Try to resolve as a short name
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{model}'. Use one from GET /api/v1/models",
        )

    try:
        instance = set_chat_model(model, provider=provider)
        return {
            "status": "ok",
            "model": model,
            "provider": provider,
            "model_type": type(instance).__name__,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to switch model: {exc}"
        ) from exc


# =============================================================================
# System Prompt (read-only via EvoScientist.EvoScientist.SYSTEM_PROMPT)
# =============================================================================


@router.get("/system-prompt")
def get_system_prompt(current_user: User = Depends(get_current_user)):
    """Return the current EvoScientist system prompt.

    Reads ``SYSTEM_PROMPT`` from EvoScientist.EvoScientist which assembles
    the full prompt from identity, experiment workflow, writing guidelines,
    delegation strategy, and async notifications components.
    """
    from ....EvoScientist import SYSTEM_PROMPT

    prompt = SYSTEM_PROMPT
    return {
        "system_prompt": prompt,
        "length": len(prompt),
    }


# =============================================================================
# Cron Schedule Management (via EvoScientist.cron.schedule)
# =============================================================================


@router.get("/schedules")
def list_schedules(current_user: User = Depends(get_current_user)):
    """List all scheduled cron tasks.

    Uses ``list_schedules()`` from EvoScientist.cron.schedule.
    """
    from ....cron.schedule import is_available, list_schedules

    if not is_available():
        raise HTTPException(
            status_code=503,
            detail="LangGraph dev server is not running. Start it with EvoSci deploy.",
        )

    crons = list_schedules()
    return {
        "schedules": [
            {
                "cron_id": c["cron_id"],
                "name": c.get("metadata", {}).get("name", ""),
                "schedule": c.get("schedule", ""),
                "prompt": (c.get("metadata", {}) or {}).get("prompt", ""),
                "enabled": c.get("enabled", True),
                "created_at": c.get("created_at", ""),
                "updated_at": c.get("updated_at", ""),
            }
            for c in crons
        ]
    }


@router.post("/schedules", status_code=status.HTTP_201_CREATED)
def create_schedule(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Create a recurring scheduled agent task.

    Uses ``create_schedule()`` from EvoScientist.cron.schedule.
    ``schedule`` is a cron expression (e.g. ``0 9 * * 1`` for weekly Monday).
    The ``prompt`` is sent to the scheduler graph on each trigger.
    """
    from ....cron.schedule import create_schedule, is_available

    if not is_available():
        raise HTTPException(
            status_code=503,
            detail="LangGraph dev server is not running.",
        )

    name = body.get("name", "").strip()
    schedule = body.get("schedule", "").strip()
    prompt = body.get("prompt", "").strip()
    timezone = body.get("timezone")

    if not name or not schedule or not prompt:
        raise HTTPException(
            status_code=400, detail="name, schedule, and prompt are required"
        )

    try:
        cron = create_schedule(
            name=name,
            schedule=schedule,
            prompt=prompt,
            timezone=timezone,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create schedule: {exc}"
        ) from exc

    return {
        "status": "created",
        "cron_id": str(cron.get("cron_id", "")),
        "name": name,
        "schedule": schedule,
    }


@router.post("/schedules/{cron_id}/toggle")
def toggle_schedule(
    cron_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Enable or disable a scheduled task.

    Uses ``set_enabled()`` from EvoScientist.cron.schedule.
    """
    from ....cron.schedule import is_available, set_enabled

    if not is_available():
        raise HTTPException(
            status_code=503, detail="LangGraph dev server is not running."
        )

    enabled = body.get("enabled", True)
    try:
        set_enabled(cron_id, enabled=enabled)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to toggle schedule: {exc}"
        ) from exc

    return {"status": "updated", "cron_id": cron_id, "enabled": enabled}


@router.delete("/schedules/{cron_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule_endpoint(
    cron_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a scheduled task.

    Uses ``delete_schedule()`` from EvoScientist.cron.schedule.
    """
    from ....cron.schedule import delete_schedule, is_available

    if not is_available():
        raise HTTPException(
            status_code=503, detail="LangGraph dev server is not running."
        )

    try:
        delete_schedule(cron_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete schedule: {exc}"
        ) from exc


@router.post("/schedules/run-now")
def run_schedule_now(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Fire a one-off scheduled task run immediately.

    Uses ``run_now()`` from EvoScientist.cron.schedule.
    """
    from ....cron.schedule import is_available, run_now

    if not is_available():
        raise HTTPException(
            status_code=503, detail="LangGraph dev server is not running."
        )

    prompt = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    try:
        run = run_now(prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to run schedule: {exc}"
        ) from exc

    return {"status": "started", "thread_id": str(run.get("thread_id", ""))}
