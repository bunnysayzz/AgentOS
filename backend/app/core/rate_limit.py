"""Lightweight in-memory rate limiting middleware.

A sliding-window counter per (route-scope, client IP) with no external
dependencies — safe for single-instance deployments (Render, Docker). For
multi-instance scale-out, swap the window store for Redis (the app already
ships ``redis`` + ``celery`` in requirements).

Limits (configurable via env):

- ``RATE_LIMIT_ENABLED`` (default true)
- ``RATE_LIMIT_AUTH_PER_MIN`` — /auth/* (default 20/min/IP)
- ``RATE_LIMIT_CHAT_PER_MIN`` — /mcp/chat/* (default 60/min/IP)
- ``RATE_LIMIT_DEFAULT_PER_MIN`` — everything else (default 300/min/IP)
"""

import time
from collections import defaultdict, deque
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.config import settings


class RateLimitExceeded(Exception):
    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"Rate limit exceeded: {limit} requests per minute")


class _WindowStore:
    """Sliding-window counters keyed by scope:ip."""

    _MAX_KEYS = 10_000

    def __init__(self):
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._last_access: dict[str, float] = {}

    def check_and_bump(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()

        # Opportunistic eviction: drop keys untouched for > 2 windows. This
        # keeps memory bounded on long-running public deployments.
        if len(self._windows) >= self._MAX_KEYS:
            stale = [
                k for k, last in self._last_access.items()
                if now - last > window * 2
            ]
            for k in stale:
                self._windows.pop(k, None)
                self._last_access.pop(k, None)
            # Hard cap as a last resort.
            while len(self._windows) >= self._MAX_KEYS:
                oldest = min(self._last_access, key=self._last_access.get)
                self._windows.pop(oldest, None)
                self._last_access.pop(oldest, None)

        self._last_access[key] = now
        dq = self._windows[key]
        while dq and now - dq[0] > window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True

    def clear(self, key: str) -> None:
        self._windows.pop(key, None)
        self._last_access.pop(key, None)


_store = _WindowStore()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _scope(path: str) -> str:
    if path.startswith("/api/v1/auth"):
        return "auth"
    if path.startswith("/api/v1/mcp/chat"):
        return "chat"
    return "default"


def _limit_for(scope: str) -> int:
    if scope == "auth":
        return max(getattr(settings, "RATE_LIMIT_AUTH_PER_MIN", 20), 1)
    if scope == "chat":
        return max(getattr(settings, "RATE_LIMIT_CHAT_PER_MIN", 60), 1)
    return max(getattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 300), 1)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-IP sliding-window limits on API routes."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.enabled = bool(getattr(settings, "RATE_LIMIT_ENABLED", True))

    async def dispatch(self, request: Request, call_next: Callable):
        if self.enabled and request.url.path.startswith("/api/v1"):
            ip = _client_ip(request)
            scope = _scope(request.url.path)
            limit = _limit_for(scope)
            if not _store.check_and_bump(f"{scope}:{ip}", limit):
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Too many requests. Limit is {limit} requests per minute. Please slow down.",
                    },
                    headers={"Retry-After": "60"},
                )
        return await call_next(request)


def reset_rate_limits() -> None:
    """Clear all windows (used in tests)."""
    _store._windows.clear()  # noqa: SLF001
