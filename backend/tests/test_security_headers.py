"""Tests for the security hardening headers middleware."""

from httpx import AsyncClient


async def test_security_headers_present_on_api_response(
    client: AsyncClient, auth_headers: dict
):
    """API responses must carry the full security header set."""
    resp = await client.get("/api/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200

    headers = resp.headers
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    csp = headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "upgrade-insecure-requests" in csp

    # The Firebase Auth hidden iframe + Google sign-in window MUST be frame-
    # allowed — blocking them breaks Google sign-in (the popup flow uses an
    # invisible iframe hosted on the authDomain).
    assert "frame-src https://accounts.google.com" in csp
    assert "frame-src" in csp and "https://*.firebaseapp.com" in csp

    # The Firebase Auth service worker (signInWithRedirect, hosted on the
    # authDomain) MUST be worker-allowed. Without worker-src it falls back to
    # default-src 'self', the SW can't register, the redirect result is lost
    # on Safari (ITP), and the user is bounced back to the login page forever.
    assert "worker-src https://*.firebaseapp.com" in csp
    assert "worker-src" in csp and "https://*.web.app" in csp

    # Sentry ingest must be reachable via connect-src (env-gated feature).
    assert "https://*.ingest.sentry.io" in csp

    perms = headers.get("permissions-policy", "")
    assert "camera=()" in perms
    assert "microphone=()" in perms
    assert "geolocation=()" in perms


async def test_security_headers_present_on_health(client: AsyncClient):
    """The health endpoint also gets hardened headers (SPA shell included)."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("content-security-policy", "").startswith("default-src 'self'")
