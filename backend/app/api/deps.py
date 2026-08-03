"""FastAPI dependencies for authentication and authorization (Firebase-only).

Bearer tokens are Firebase Auth ID tokens, verified against Google's public
certs. API keys are stored (hashed) in Firestore and checked in constant time.
"""

import hashlib
import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader

from app.core.db import FirestoreDB, now_iso
from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.services import auth_service

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

API_KEYS = "api_keys"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_scheme),
    db: FirestoreDB = Depends(get_db),
) -> dict:
    """Get the currently authenticated user from a Firebase token or API key."""
    if credentials:
        return _get_user_from_token(credentials.credentials, db)

    if api_key:
        return _get_user_from_api_key(api_key, db)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide a Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _get_user_from_token(token: str, db: FirestoreDB) -> dict:
    """Validate a Firebase Auth ID token and resolve/create the user."""
    try:
        claims = verify_firebase_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_service.get_or_create_user_from_firebase(db, claims)

    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


def _extract_api_key_prefix(api_key: str) -> str:
    """Extract the prefix from an API key (format: ag_{prefix}_{random})."""
    parts = api_key.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"
    return api_key


def _get_user_from_api_key(api_key: str, db: FirestoreDB) -> dict:
    """Authenticate using an API key with prefix-filtered lookup."""
    prefix = _extract_api_key_prefix(api_key)

    key = None
    for row in db.query(API_KEYS, "key_prefix", prefix):
        if row.get("is_active") and not row.get("deleted_at"):
            key = row
            break

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Verify the full key against the stored hash (SHA-256, constant-time)
    expected = hashlib.sha256(api_key.encode()).hexdigest()
    if not hmac.compare_digest(expected, key.get("key_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Update last used timestamp
    key["last_used_at"] = now_iso()
    db.set(API_KEYS, key["id"], key)

    user = auth_service.get_user_by_id(db, key["user_id"])
    if user is None or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return user


# ─── Role-based permission checks ──────────────────────


async def require_superuser(current_user: dict = Depends(get_current_user)) -> dict:
    """Require the current user to be a superuser."""
    if not current_user.get("is_superuser"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Require the current user to be active."""
    if not current_user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: FirestoreDB = Depends(get_db),
) -> dict | None:
    """Get the current user if authenticated, None otherwise."""
    if credentials is None:
        return None
    try:
        return _get_user_from_token(credentials.credentials, db)
    except HTTPException:
        return None
