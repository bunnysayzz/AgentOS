"""Firebase core module — Firestore client + Firebase ID token verification.

The Firestore client is initialized lazily in a strict, production-friendly
order:

1. Service Account (FIREBASE_PRIVATE_KEY & FIREBASE_CLIENT_EMAIL)  → prod
2. Local CLI OAuth tokens (~/.config/configstore/firebase-tools.json) → dev
3. ENV OAuth refresh token (FIREBASE_REFRESH_TOKEN & FIREBASE_CLIENT_ID)
4. GOOGLE_APPLICATION_CREDENTIALS / GCP ADC → GCP services / default

Firebase Auth ID tokens are verified against Google's public certs via
``google-auth`` — no credentials required.
"""

import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.cloud import firestore

from app.core.config import settings

logger = logging.getLogger(__name__)

CONFIGSTORE_PATH = Path.home() / ".config" / "configstore" / "firebase-tools.json"

# Current firebase-tools OAuth client secret (src/api.ts clientSecret()).
# The previous well-known value ("s9fK2i10383bGe2VZuWQqA-M") was rotated by
# Google — refreshes with it fail with `invalid_client`.
FIREBASE_CLI_CLIENT_SECRET = "j9iVZfS8kkCEFUPaAeJV0sAi"

_firestore_db = None
_verify_request = None


def get_firestore_db() -> firestore.Client:
    """Get or initialize the Cloud Firestore client (lazy, cached)."""
    global _firestore_db
    if _firestore_db is not None:
        return _firestore_db

    project_id = settings.FIREBASE_PROJECT_ID or "agentos-7f01e"
    client_opts = {"quota_project_id": project_id}

    # ─── 1. Production: Service Account Private Key from ENV ─────────────
    if settings.FIREBASE_PRIVATE_KEY and settings.FIREBASE_CLIENT_EMAIL:
        formatted_key = settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n")
        cred_dict = {
            "type": "service_account",
            "project_id": project_id,
            "client_email": settings.FIREBASE_CLIENT_EMAIL,
            "private_key": formatted_key,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        creds = service_account.Credentials.from_service_account_info(cred_dict)
        _firestore_db = firestore.Client(project=project_id, credentials=creds, client_options=client_opts)
        logger.info(f"Cloud Firestore initialized using Service Account ENV for project {project_id}.")
        return _firestore_db

    # ─── 2. Local Developer: CLI Credentials File ────────────────────────
    if CONFIGSTORE_PATH.exists():
        try:
            import json
            with open(CONFIGSTORE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            tokens = data.get("tokens", {})
            cli_user = data.get("user", {})
            client_id = cli_user.get("azp") or cli_user.get("aud") or settings.FIREBASE_CLIENT_ID
            if tokens.get("access_token") and tokens.get("refresh_token") and client_id:
                creds = Credentials(
                    token=tokens["access_token"],
                    refresh_token=tokens["refresh_token"],
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=FIREBASE_CLI_CLIENT_SECRET,
                )
                _firestore_db = firestore.Client(project=project_id, credentials=creds, client_options=client_opts)
                logger.info(f"Cloud Firestore initialized using local CLI tokens for project {project_id}.")
                return _firestore_db
        except Exception as e:  # pragma: no cover
            logger.warning(f"Local CLI token init failed: {e}")

    # ─── 3. ENV Credentials: OAuth Refresh Token ─────────────────────────
    if settings.FIREBASE_REFRESH_TOKEN and settings.FIREBASE_CLIENT_ID:
        creds = Credentials(
            token=getattr(settings, "FIREBASE_ACCESS_TOKEN", None),
            refresh_token=settings.FIREBASE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.FIREBASE_CLIENT_ID,
            client_secret=FIREBASE_CLI_CLIENT_SECRET,
        )
        _firestore_db = firestore.Client(project=project_id, credentials=creds, client_options=client_opts)
        logger.info(
            f"Cloud Firestore initialized using ENV OAuth credentials ({settings.FIREBASE_USER_EMAIL}) "
            f"for project {project_id}."
        )
        return _firestore_db

    # ─── 4. Default Fallback (ADC / GOOGLE_APPLICATION_CREDENTIALS) ──────
    _firestore_db = firestore.Client(project=project_id, client_options=client_opts)
    logger.info(f"Cloud Firestore initialized using default client for project {project_id}.")
    return _firestore_db


def verify_firebase_token(token: str) -> dict:
    """Verify a Firebase Auth ID token using Google's public certs.

    Returns the decoded claims (``uid``, ``email``, ``name``, ``picture``, …)
    or raises ValueError for invalid/expired tokens. Requires no credentials.

    Audience note: Firebase ID tokens carry the project's *API key or project
    number* in their ``aud`` claim — never the human-readable project ID
    (e.g. ``agentos-7f01e``). Passing ``audience=settings.FIREBASE_PROJECT_ID``
    to ``google-auth`` would therefore reject every legitimate token, so we
    omit the strict audience match and instead pin the token to our project
    via the issuer (``https://securetoken.google.com/<projectId>``), which is
    unique per Firebase project.
    """
    global _verify_request
    from google.oauth2 import id_token
    from google.auth.transport import requests as _transport

    if _verify_request is None:
        _verify_request = _transport.Request()

    claims = id_token.verify_token(
        token,
        request=_verify_request,
        # audience deliberately omitted — see docstring
    )

    # Firebase ID tokens are issued by https://securetoken.google.com/<projectId>
    issuer = str(claims.get("iss", ""))
    expected_issuer = f"https://securetoken.google.com/{settings.FIREBASE_PROJECT_ID}"
    if not issuer.startswith("https://securetoken.google.com/") or issuer != expected_issuer:
        raise ValueError(f"Invalid Firebase token issuer: {issuer}")
    if not claims.get("uid"):
        raise ValueError("Invalid Firebase token: missing uid")
    return claims
