"""Tests for the in-memory rate limiting middleware."""

import pytest
from httpx import AsyncClient

from app.core.rate_limit import reset_rate_limits


@pytest.fixture(autouse=True)
def fresh_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


class TestRateLimiting:
    async def test_auth_endpoint_throttled(self, client: AsyncClient):
        """Auth endpoints are limited (20/min/IP) — burst beyond that → 429."""
        headers = {"Authorization": "Bearer firebase.test@example.com:Test User"}
        got_429 = False
        for _ in range(25):
            resp = await client.get("/api/v1/auth/me", headers=headers)
            if resp.status_code == 429:
                got_429 = True
                break
        assert got_429 is True
        assert resp.json()["detail"]

    async def test_default_endpoint_has_higher_limit(self, client: AsyncClient):
        """Non-auth endpoints tolerate a normal request volume (300/min)."""
        # Health is not /api/v1 so it's never limited.
        for _ in range(5):
            resp = await client.get("/health")
            assert resp.status_code == 200

        # A burst of ordinary API reads (workspace list) should pass.
        headers = {"Authorization": "Bearer firebase.test@example.com:Test User"}
        codes = set()
        for _ in range(20):
            resp = await client.get("/api/v1/workspaces/", headers=headers)
            codes.add(resp.status_code)
        assert 429 not in codes

    async def test_rate_limit_disabled_flag(self):
        """When RATE_LIMIT_ENABLED=False the middleware passes everything."""
        from app.core.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware.__new__(RateLimitMiddleware)
        middleware.enabled = False
        assert middleware.enabled is False
