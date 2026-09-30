"""AI usage endpoints: what the AI consumed, and for whose work.

Students see their own usage; professors and admins can look at one person, one
project, one paper, or the whole platform. Token figures keep provider-reported
and estimated counts apart, so a number is never presented as a measurement when
it is an estimate.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...crud.ai_usage import list_usage, summarize_usage
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user
from ..schemas import AiUsageRecord, AiUsageRecords, AiUsageSummary

router = APIRouter()


def _is_supervisor(user: User) -> bool:
    return user.is_admin or user.role in ("professor", "admin")


@router.get("/usage/summary", response_model=AiUsageSummary)
def ai_usage_summary(
    scope: str = Query(default="me", pattern="^(me|user|all)$"),
    user_id: str | None = Query(default=None, description="Required when scope=user"),
    project_id: str | None = Query(default=None),
    publication_id: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
):
    """Aggregate AI usage over a time window."""
    target_user = _resolve_target_user(scope, user_id, current_user)
    summary = summarize_usage(
        get_db_path(),
        user_id=target_user,
        project_id=project_id,
        publication_id=publication_id,
        days=days,
    )
    return AiUsageSummary(
        window_days=summary["window_days"],
        calls=summary["calls"],
        tokens=summary["tokens"],
        avg_duration_ms=summary["avg_duration_ms"],
        by_task=[
            {
                "label": row["task"],
                "calls": row["calls"],
                "provider_tokens": row["provider_tokens"],
                "estimated_tokens": row["estimated_tokens"],
            }
            for row in summary["by_task"]
        ],
        by_model=[
            {
                "label": row["model"],
                "calls": row["calls"],
                "provider_tokens": row["provider_tokens"],
                "estimated_tokens": row["estimated_tokens"],
            }
            for row in summary["by_model"]
        ],
    )


@router.get("/usage/records", response_model=AiUsageRecords)
def ai_usage_records(
    scope: str = Query(default="me", pattern="^(me|user|all)$"),
    user_id: str | None = Query(default=None, description="Required when scope=user"),
    project_id: str | None = Query(default=None),
    publication_id: str | None = Query(default=None),
    days: int | None = Query(default=None, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
):
    """The most recent AI calls, newest first."""
    target_user = _resolve_target_user(scope, user_id, current_user)
    rows = list_usage(
        get_db_path(),
        user_id=target_user,
        project_id=project_id,
        publication_id=publication_id,
        days=days,
        limit=limit,
    )
    return AiUsageRecords(
        records=[
            AiUsageRecord(
                id=r.id,
                task=r.task,
                source=r.source,
                token_source=r.token_source,
                model=r.model,
                user_id=r.user_id,
                project_id=r.project_id,
                publication_id=r.publication_id,
                run_id=r.run_id,
                prompt_tokens=r.prompt_tokens,
                completion_tokens=r.completion_tokens,
                total_tokens=r.total_tokens,
                duration_ms=r.duration_ms,
                created_at=r.created_at,
            )
            for r in rows
        ]
    )


def _resolve_target_user(scope: str, user_id: str | None, current_user: User) -> str | None:
    """Turn a scope into a user filter, refusing to widen access silently."""
    if scope == "all":
        if not _is_supervisor(current_user):
            raise HTTPException(status_code=403, detail="Not permitted")
        return None
    if scope == "user":
        if not user_id:
            raise HTTPException(status_code=422, detail="user_id is required for scope=user")
        if user_id != current_user.id and not _is_supervisor(current_user):
            raise HTTPException(status_code=403, detail="Not permitted")
        return user_id
    # scope == "me"
    return current_user.id
