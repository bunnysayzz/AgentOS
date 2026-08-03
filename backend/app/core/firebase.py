"""Firebase core module — Firestore client + Firebase ID token verification.

The Firestore client is initialized lazily in a strict, production-friendly
order:

1. Service Account (FIREBASE_PRIVATE_KEY & FIREBASE_CLIENT_EMAIL)  → prod
2. Local CLI OAuth tokens (~/.config/configstore/firebase-tools.json) → dev
3. ENV OAuth refresh token (FIREBASE_REFRESH_TOKEN & FIREBASE_CLIENT_ID)
4. GOOGLE_APPLICATION_CREDENTIALS / GCP ADC → GCP services / default

Firebase Auth ID tokens are verified against **Firebase's** public signing
certs (``securetoken@system.gserviceaccount.com``). This is important:
``google.oauth2.id_token.verify_token`` uses Google OAuth certs and rejects
Firebase ID tokens with ``Certificate for key id ... not found``. We instead
use ``google.auth.jwt.decode`` with the Firebase certs endpoint directly.
"""

import json
import logging
import time
from pathlib import Path

from google.auth import jwt as gauth_jwt
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

# Firebase ID tokens are signed by Firebase's own certs, published here.
FIREBASE_CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)

_firestore_db = None
_verify_request = None
_certs = None
_certs_fetched_at = 0.0
CERT_TTL_SECONDS = 3600  # re-fetch signing certs hourly


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
        # Normalize empty-string access token to None. An empty string makes
        # google-auth think it has a valid token and send a blank Bearer
        # header -> Firestore responds 403 (no refresh is ever attempted).
        access_token = (settings.FIREBASE_ACCESS_TOKEN or "").strip() or None
        creds = Credentials(
            token=access_token,
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


def _fetch_firebase_certs() -> dict:
    """Fetch (and cache) Firebase's public signing certs for ID tokens."""
    global _certs, _certs_fetched_at
    global _verify_request

    now = time.time()
    if _certs is not None and now - _certs_fetched_at < CERT_TTL_SECONDS:
        return _certs

    from google.auth.transport import requests as _transport

    if _verify_request is None:
        _verify_request = _transport.Request()

    response = _verify_request(FIREBASE_CERTS_URL, method="GET")
    if response.status != 200:
        raise ValueError("Failed to fetch Firebase signing certificates")
    _certs = json.loads(response.data.decode("utf-8"))
    _certs_fetched_at = now
    return _certs


def verify_firebase_token(token: str) -> dict:
    """Verify a Firebase Auth ID token using Firebase's signing certs.

    Returns the decoded claims (``user_id``/``sub``, ``email``, ``name``,
    ``picture``, …) or raises ValueError for invalid/expired tokens.
    Requires no credentials — only Google's public certs.

    Security checks:
    - Signature + expiry verified via ``google.auth.jwt.decode``.
    - ``aud`` must equal the project ID (Firebase sets ``aud`` to the project
      ID on ID tokens, e.g. ``agentos-7f01e``).
    - ``iss`` must be ``https://securetoken.google.com/<projectId>`` — unique
      per Firebase project, so tokens from other projects are rejected.
    """
    project_id = settings.FIREBASE_PROJECT_ID or "agentos-7f01e"
    certs = _fetch_firebase_certs()

    claims = gauth_jwt.decode(
        token,
        certs=certs,
        audience=project_id,
        clock_skew_in_seconds=30,
    )

    # Pinning: issuer must be this project's securetoken URL.
    issuer = str(claims.get("iss", ""))
    expected_issuer = f"https://securetoken.google.com/{project_id}"
    if issuer != expected_issuer:
        raise ValueError(f"Invalid Firebase token issuer: {issuer}")

    # Firebase uses ``user_id``/``sub`` for the account id (no ``uid`` claim).
    uid = claims.get("user_id") or claims.get("sub") or claims.get("uid")
    if not uid:
        raise ValueError("Invalid Firebase token: missing user id")
    claims["uid"] = uid
    return claims
