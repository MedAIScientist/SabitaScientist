"""FastAPI middleware that logs all mutating requests to the audit log."""

from __future__ import annotations

import json

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ..crud.audit import log_action as _log_action
from ..db import get_db_path


class AuditMiddleware(BaseHTTPMiddleware):
    """Logs POST/PUT/PATCH/DELETE API requests to the audit_log table.

    Captures: user ID (from token), action, entity type, entity ID (from path),
    request details, IP address, and timestamp.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)
        if "/api/v1/" not in request.url.path:
            return await call_next(request)
        if request.url.path.endswith("/login"):
            return await call_next(request)

        response = await call_next(request)

        if 200 <= response.status_code < 300:
            self._log(request, response)

        return response

    def _log(self, request: Request, response: Response) -> None:
        path = request.url.path
        method = request.method

        # Extract entity type from path
        parts = path.replace("/api/v1/", "").split("/")
        entity_type = parts[0] if parts else "unknown"

        # Extract entity ID from path (typically the second segment after the type)
        entity_id = parts[1] if len(parts) > 1 and parts[1] and not parts[1].startswith("search") else None

        # Extract user ID from auth header
        user_id = None
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            from ..auth import validate_token
            user_id = validate_token(auth[7:], get_db_path())

        action = method.lower()
        details = json.dumps({
            "path": path,
            "method": method,
            "status": response.status_code,
        })

        ip = request.client.host if request.client else None

        try:
            _log_action(
                get_db_path(),
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
                ip_address=ip,
            )
        except Exception:
            pass
