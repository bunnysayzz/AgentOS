"""API Key service - create, list, revoke, and validate API keys."""

import secrets
import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.schemas.user import ApiKeyCreate


# ─── Errors ──────────────────────────────────────────


class ApiKeyError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ApiKeyNotFoundError(ApiKeyError):
    def __init__(self):
        super().__init__("API key not found", status_code=404)


# ─── Key Generation ─────────────────────────────────


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.
    
    Returns: (full_key, key_prefix, key_hash)
    Format: agos_{prefix}_{secret}
    """
    prefix = secrets.token_hex(4)  # 8 chars
    secret = secrets.token_hex(24)  # 48 chars
    full_key = f"agos_{prefix}_{secret}"
    key_prefix = f"agos_{prefix}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_prefix, key_hash


# ─── CRUD ──────────────────────────────────────────


async def create_api_key(
    db: AsyncSession, user_id: UUID, key_in: ApiKeyCreate
) -> tuple[ApiKey, str]:
    """Create a new API key for a user. Returns (key_record, full_key)."""
    full_key, key_prefix, key_hash = generate_api_key()

    api_key = ApiKey(
        user_id=user_id,
        name=key_in.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=",".join(key_in.scopes) if key_in.scopes else None,
        expires_at=key_in.expires_at,
        is_active=True,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)
    return api_key, full_key


async def list_user_api_keys(
    db: AsyncSession, user_id: UUID
) -> list[ApiKey]:
    """List all API keys for a user."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def get_api_key_by_id(
    db: AsyncSession, key_id: UUID, user_id: UUID
) -> ApiKey | None:
    """Get a specific API key by ID (scoped to user)."""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def revoke_api_key(
    db: AsyncSession, key_id: UUID, user_id: UUID
) -> None:
    """Revoke (soft-delete) an API key."""
    api_key = await get_api_key_by_id(db, key_id, user_id)
    if api_key is None:
        raise ApiKeyNotFoundError()
    api_key.is_active = False
    await db.flush()


async def delete_api_key(
    db: AsyncSession, key_id: UUID, user_id: UUID
) -> None:
    """Permanently delete an API key."""
    api_key = await get_api_key_by_id(db, key_id, user_id)
    if api_key is None:
        raise ApiKeyNotFoundError()
    await db.delete(api_key)
    await db.flush()
