from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...crud.audit import list_logs
from ...db import get_db_path
from ...models import User
from ..deps import require_admin

router = APIRouter()


@router.get("/audit/logs")
def get_audit_logs(
    current_user: User = Depends(require_admin),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    db = get_db_path()
    logs = list_logs(db, entity_type=entity_type, entity_id=entity_id, user_id=user_id, limit=limit)
    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "action": e.action,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "details": e.details,
            "created_at": e.created_at,
        }
        for e in logs
    ]
