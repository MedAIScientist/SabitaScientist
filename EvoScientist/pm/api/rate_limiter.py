"""Simple in-memory rate limiter middleware — per-IP request throttling."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate-limits requests per IP. Configure via RATE_LIMIT env var."""

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Only rate-limit API endpoints
        if "/api/v1/" not in request.url.path:
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time.time()
        self._requests[ip] = [t for t in self._requests[ip] if now - t < self.window]

        if len(self._requests[ip]) >= self.max_requests:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})

        self._requests[ip].append(now)
        return await call_next(request)
