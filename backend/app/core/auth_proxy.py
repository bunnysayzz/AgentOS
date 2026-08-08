"""Firebase auth-helper reverse proxy (Firebase's documented "Option 3").

Google sign-in is delivered through sign-in helper code hosted on the
Firebase auth domain (``<project>.firebaseapp.com/__/auth/*``). When the app
is hosted on a DIFFERENT origin (Render, Vercel, your own server), that
helper is cross-origin — and browsers that block third-party storage access
(Safari 16.1+, Chrome 115+, Firefox 109+) then break sign-in: the popup
handshake fails with ``auth/internal-error`` and the redirect return trip
silently never completes, stranding users on the login page.

Firebase's documented fix (https://firebase.google.com/docs/auth/web/redirect-best-practices,
"Option 3: Proxy auth requests to firebaseapp.com") is to transparently
reverse-proxy ``/__/auth`` on the APP origin to ``<project>.firebaseapp.com``.
The browser then sees the helper as SAME-origin: no cross-site storage
access, no ITP partitioning, sign-in works everywhere.

Must be a transparent proxy (NOT a 302 redirect) — the sign-in helper needs
to read/write storage on the app origin for the flow to complete.
"""

import logging

import httpx
from fastapi import FastAPI, Request
from starlette.responses import Response

from app.core.config import settings

logger = logging.getLogger(__name__)

# Hop-by-hop headers must never be forwarded upstream (HTTP/1.1 semantics).
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

# A single shared client keeps connection pooling cheap (the helper is
# contacted on every auth iframe load / popup open).
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        target = settings.FIREBASE_AUTH_PROXY_TARGET or (
            f"https://{settings.FIREBASE_PROJECT_ID or 'agentos-7f01e'}.firebaseapp.com"
        )
        _client = httpx.AsyncClient(
            base_url=target,
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=False,
        )
        logger.info(f"Firebase auth-helper proxy target: {target}")
    return _client


def _clean_headers(headers: httpx.Headers) -> dict[str, str]:
    """Drop hop-by-hop + Host headers before forwarding upstream."""
    return {
        k: v
        for k, v in headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() not in {"host", "content-length"}
    }


async def _proxy(request: Request) -> Response:
    """Forward one request to the Firebase auth domain and stream it back."""
    # Preserve the full path + query string, e.g. /__/auth/iframe?apiKey=…
    # (Starlette exposes request.url.query as a str; httpx.URL wants bytes.)
    url = httpx.URL(
        path=request.url.path,
        query=request.url.query.encode("latin-1"),
    )
    body = await request.body()
    upstream = await _get_client().request(
        request.method,
        url,
        headers=_clean_headers(request.headers),
        content=body or None,
    )

    response_headers = {}
    for k, v in upstream.headers.items():
        if k.lower() not in _HOP_BY_HOP:
            response_headers[k] = v

    # The proxied helper responses must NOT inherit the app's frame-blocking
    # headers — the auth iframe has to be frameable by the app page. The
    # security-headers middleware already skips /__/ paths (see
    # security_headers.py), so just don't re-add anything here.
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )


def register_auth_proxy(app: FastAPI) -> None:
    """Mount the transparent /__/auth and /__/firebase proxy routes.

    Must be called BEFORE the SPA ``/{full_path:path}`` catch-all route so
    these paths are never swallowed by the SPA fallback.
    """
    app.add_api_route(
        "/__/auth/{path:path}",
        _proxy,
        methods=["GET", "POST", "HEAD", "OPTIONS", "PUT", "DELETE", "PATCH"],
        include_in_schema=False,
    )
    app.add_api_route(
        "/__/firebase/{path:path}",
        _proxy,
        methods=["GET", "POST", "HEAD", "OPTIONS", "PUT", "DELETE", "PATCH"],
        include_in_schema=False,
    )
