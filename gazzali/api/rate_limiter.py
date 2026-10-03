"""Simple rate limiter middleware — per-IP request throttling.

Supports two backends:
- ``memory`` (default) — single-process, fast, resets on restart.
- ``sqlite``   — multi-worker safe, persists across restarts via PM database.

Set ``RATE_LIMIT_BACKEND=sqlite`` env var to enable the SQLite backend.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate-limits requests per IP. Configure via ``max_requests`` and ``window_seconds``."""

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds
        self._use_sqlite = os.environ.get("RATE_LIMIT_BACKEND", "memory") == "sqlite"
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if "/api/v1/" not in request.url.path:
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - self.window
        count = 0

        if self._use_sqlite:
            count = self._check_sqlite(ip, now, cutoff)
        else:
            count = self._check_memory(ip, now, cutoff)

        if count >= self.max_requests:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})

        return await call_next(request)

    def _check_memory(self, ip: str, now: float, cutoff: float) -> int:
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]
        self._requests[ip].append(now)
        return len(self._requests[ip])

    def _check_sqlite(self, ip: str, now: float, cutoff: float) -> int:
        try:
            from pathlib import Path

            from ..db import get_db, get_db_path
            with get_db(Path(get_db_path())) as conn:
                conn.execute(
                    "DELETE FROM rate_limits WHERE ip = ? AND requested_at < ?",
                    (ip, cutoff),
                )
                conn.execute(
                    "INSERT INTO rate_limits (ip, requested_at) VALUES (?, ?)",
                    (ip, now),
                )
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM rate_limits WHERE ip = ?",
                    (ip,),
                ).fetchone()
                return row["cnt"] if row else 1
        except Exception:
            return 0  # fall open if DB is unavailable
