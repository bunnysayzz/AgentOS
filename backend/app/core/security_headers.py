"""Security hardening headers middleware.

Sets the security headers a production SaaS should ship:

- ``Content-Security-Policy`` — allow only what the SPA actually needs:
  itself, Google Fonts, Firebase Auth endpoints, Firebase Storage, the
  Google sign-in window, the Firebase Auth hidden iframe (drives the
  Google popup flow), and (optionally) Sentry + a configured analytics
  host. Everything else is denied by default.
- ``X-Frame-Options: DENY`` — blocks clickjacking (the SPA never needs to
  be framed).
- ``Strict-Transport-Security`` — HTTPS-only (skipped in DEBUG / plain HTTP).
- ``X-Content-Type-Options: nosniff`` — prevents MIME-sniffing attacks.
- ``Referrer-Policy`` — limits what URLs leak to third parties.
- ``Permissions-Policy`` — denies camera/mic/geolocation/etc. by default.

All headers are additive (setdefault), so anything set by the app (e.g. the
cache-control middleware) is never clobbered.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.core.config import settings

# ─── CSP ────────────────────────────────────────────────────────────────────
# Resources the production SPA legitimately loads:
#   self                          → JS bundle, CSS, API (same origin)
#   fonts.googleapis/gstatic      → Google Fonts (preconnect in index.html)
#   identitytoolkit.googleapis    → Firebase Auth (email/password, ID tokens)
#   securetoken.googleapis        → Firebase Auth token refresh
#   www.googleapis.com            → Google sign-in API
#   firebasestorage.googleapis    → avatar uploads/downloads
#   storage.googleapis.com        → avatar CDN URLs
#   lh3.googleusercontent.com     → Google profile photos
#   accounts.google.com           → Google sign-in popup window
#   *.firebaseapp.com / *.web.app → Firebase Auth HIDDEN IFRAME (drives the
#                                   Google popup flow — without it, sign-in
#                                   silently never completes)
#   raw.githubusercontent.com     → marketing banner assets
#
# frame-src must include the authDomain because signInWithPopup uses a
# popup PLUS an invisible auth iframe hosted on the authDomain
# (https://<authDomain>/__/auth/iframe). Blocking it breaks Google sign-in.
# worker-src must include it too: signInWithRedirect registers the auth
# service worker from the authDomain (https://<authDomain>/__/auth/
# firebase-auth-sw.js) so the redirect result survives Safari ITP. Without
# worker-src, the SW can't register, the result is lost on return, and the
# user is bounced back to the login page ("login never confirms").
_CSP_CONNECT_EXTRA = [
    # Sentry error tracking ingest (only reached when SENTRY_DSN is set).
    "https://*.ingest.sentry.io",
]
if getattr(settings, "CSP_EXTRA_CONNECT_SRC", ""):
    _CSP_CONNECT_EXTRA.append(settings.CSP_EXTRA_CONNECT_SRC)

_CSP_SCRIPT_EXTRA = []
if getattr(settings, "CSP_EXTRA_SCRIPT_SRC", ""):
    _CSP_SCRIPT_EXTRA.append(settings.CSP_EXTRA_SCRIPT_SRC)

_CSP = (
    "default-src 'self'; "
    "script-src 'self'" + (" " + " ".join(_CSP_SCRIPT_EXTRA) if _CSP_SCRIPT_EXTRA else "") + "; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob: https://firebasestorage.googleapis.com "
    "https://storage.googleapis.com https://lh3.googleusercontent.com "
    "https://raw.githubusercontent.com; "
    "connect-src 'self' https://identitytoolkit.googleapis.com "
    "https://securetoken.googleapis.com https://www.googleapis.com "
    "https://firebasestorage.googleapis.com https://storage.googleapis.com"
    + (" " + " ".join(_CSP_CONNECT_EXTRA) if _CSP_CONNECT_EXTRA else "")
    + "; "
    "frame-src 'self' https://accounts.google.com https://*.firebaseapp.com https://*.web.app; "
    "worker-src 'self' https://*.firebaseapp.com https://*.web.app; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "upgrade-insecure-requests"
)


def _security_headers(request: Request) -> dict[str, str]:
    # The Firebase auth-helper proxy (/__/auth, /__/firebase) serves Google's
    # sign-in helper code on OUR origin. Those responses must NOT inherit the
    # app's frame-blocking headers — the auth iframe has to be frameable by
    # the app page (X-Frame-Options: DENY / frame-ancestors 'none' would break
    # Google sign-in). Serve them exactly as upstream does (only HSTS added).
    if request.url.path.startswith("/__/"):
        headers: dict[str, str] = {}
        if not settings.DEBUG and request.url.scheme == "https":
            headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        return headers

    headers = {
        "Content-Security-Policy": _CSP,
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": (
            "camera=(), microphone=(), geolocation=(), payment=(), "
            "usb=(), display-capture=(), fullscreen=()"
        ),
    }
    # HSTS only makes sense over real HTTPS and must not lock out local dev.
    if not settings.DEBUG and request.url.scheme == "https":
        headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
    return headers


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every response (never overriding existing)."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for name, value in _security_headers(request).items():
            response.headers.setdefault(name, value)
        return response
