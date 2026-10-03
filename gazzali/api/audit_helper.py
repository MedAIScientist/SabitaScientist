"""Helper to log audit entries from API routes."""

from __future__ import annotations

from fastapi import Request

from ..crud.audit import log_action as _log_action
from ..db import get_db_path
from ..models import User


def log_action(
    request: Request,
    current_user: User,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: str | None = None,
) -> None:
    """Log an audit entry using the request's IP and current user."""
    ip = request.client.host if request.client else None
    _log_action(
        get_db_path(),
        user_id=current_user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip,
    )
