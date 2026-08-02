"""FastAPI dependencies for authentication and authorization."""

import hashlib
import hmac
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token, pwd_context
from app.models.api_key import ApiKey
from app.models.user import User
from app.services import auth_service

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the currently authenticated user from JWT or API key."""
    if credentials:
        return await _get_user_from_token(credentials.credentials, db)

    if api_key:
        return await _get_user_from_api_key(api_key, db)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide a Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _get_user_from_token(token: str, db: AsyncSession) -> User:
    """Extract and validate user from a JWT or Firebase Auth ID token."""
    payload = decode_token(token)
    if not payload:
        # Try Firebase Auth ID Token Verification
        try:
            from firebase_admin import auth as fb_auth
            fb_decoded = fb_auth.verify_id_token(token)
            email = fb_decoded.get("email") or f"{fb_decoded['uid']}@agentos.studio"
            stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                user = User(
                    email=email,
                    username=fb_decoded.get("name") or email.split("@")[0],
                    full_name=fb_decoded.get("name", "Google User"),
                    hashed_password=pwd_context.hash(fb_decoded["uid"]),
                    is_active=True,
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
            return user
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = UUID(subject)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )

    user = await auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


def _extract_api_key_prefix(api_key: str) -> str:
    """Extract the prefix from an API key for DB lookup.
    
    API keys follow the format: ag_{prefix}_{random}
    Where the prefix is everything before the second underscore.
    Example: ag_a1b2c3d4_e5f6g7h8... -> prefix is 'ag_a1b2c3d4'
    This must match whatever was stored as key_prefix at creation time.
    """
    parts = api_key.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"
    return api_key


async def _get_user_from_api_key(api_key: str, db: AsyncSession) -> User:
    """Authenticate using an API key with prefix-filtered lookup."""
    prefix = _extract_api_key_prefix(api_key)

    # First, narrow by prefix for fast lookup
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == prefix,
            ApiKey.is_active.is_(True),
            ApiKey.deleted_at.is_(None),
        )
    )
    key = result.scalar_one_or_none()

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Verify the full key against the stored hash (SHA-256, constant-time)
    expected = hashlib.sha256(api_key.encode()).hexdigest()
    if not hmac.compare_digest(expected, key.key_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Update last used timestamp
    key.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    user = await auth_service.get_user_by_id(db, key.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return user


# ─── Role-based permission checks ──────────────────────


async def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    """Require the current user to be a superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Require the current user to be active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Get the current user if authenticated, None otherwise."""
    if credentials is None:
        return None
    try:
        return await _get_user_from_token(credentials.credentials, db)
    except HTTPException:
        return None
