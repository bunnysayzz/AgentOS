"""Secrets Manager service - encrypted storage, CRUD, vault integration."""

import base64
import os
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.models.secret import Secret, SecretProvider
from app.schemas.secret import SecretCreate, SecretUpdate
from app.core.config import settings


# ─── Encryption ────────────────────────────────────


def _get_fernet() -> Fernet:
    """Get a Fernet instance using the configured encryption key."""
    # Derive a 32-byte key from the configured encryption key
    key = settings.ENCRYPTION_KEY.encode()
    salt = b"agentos_studio_salt"  # Fixed salt for deterministic key
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    fernet_key = base64.urlsafe_b64encode(kdf.derive(key))
    return Fernet(fernet_key)


def encrypt_value(value: str) -> str:
    """Encrypt a secret value."""
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Decrypt a secret value."""
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()


# ─── Errors ──────────────────────────────────────────


class SecretError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class SecretNotFoundError(SecretError):
    def __init__(self):
        super().__init__("Secret not found", status_code=404)


class SecretSlugTakenError(SecretError):
    def __init__(self):
        super().__init__("A secret with this slug already exists in this workspace", status_code=409)


# ─── CRUD ──────────────────────────────────────────


async def create_secret(db: AsyncSession, workspace_id: UUID, secret_in: SecretCreate) -> Secret:
    """Create a new secret (value is encrypted before storage)."""
    # Auto-generate slug from name if not provided
    slug = secret_in.slug
    if slug is None:
        slug = secret_in.name.lower().replace(" ", "_").replace("-", "_")
        slug = "".join(c for c in slug if c.isalnum() or c == "_")
        if not slug:
            slug = "secret"

    # Check slug uniqueness within workspace
    result = await db.execute(
        select(Secret).where(
            Secret.workspace_id == workspace_id,
            Secret.slug == slug,
            Secret.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none():
        raise SecretSlugTakenError()

    encrypted = encrypt_value(secret_in.value)

    secret = Secret(
        workspace_id=workspace_id,
        name=secret_in.name,
        slug=slug,
        description=secret_in.description,
        encrypted_value=encrypted,
        provider=secret_in.provider,
        environment=secret_in.environment,
    )
    db.add(secret)
    await db.flush()
    await db.refresh(secret)
    return secret


async def get_secret_by_id(db: AsyncSession, secret_id: UUID) -> Secret | None:
    result = await db.execute(
        select(Secret).where(Secret.id == secret_id, Secret.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_secret_value(db: AsyncSession, secret_id: UUID) -> str | None:
    """Get a secret's decrypted value (for internal use by other services)."""
    secret = await get_secret_by_id(db, secret_id)
    if secret is None or not secret.encrypted_value:
        return None
    try:
        return decrypt_value(secret.encrypted_value)
    except Exception:
        return None


async def list_workspace_secrets(
    db: AsyncSession, workspace_id: UUID, page: int = 1, page_size: int = 50
) -> tuple[list[Secret], int]:
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(Secret.id)).where(
            Secret.workspace_id == workspace_id,
            Secret.deleted_at.is_(None),
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Secret)
        .where(Secret.workspace_id == workspace_id, Secret.deleted_at.is_(None))
        .order_by(Secret.name.asc())
        .offset(offset).limit(page_size)
    )
    return list(result.scalars().all()), total


async def update_secret(db: AsyncSession, secret: Secret, secret_in: SecretUpdate) -> Secret:
    """Update a secret. If value is provided, it's re-encrypted."""
    update_data = secret_in.model_dump(exclude_unset=True)

    if "value" in update_data:
        secret.encrypted_value = encrypt_value(update_data.pop("value"))

    for field, value in update_data.items():
        setattr(secret, field, value)

    await db.flush()
    await db.refresh(secret)
    return secret


async def delete_secret(db: AsyncSession, secret: Secret) -> None:
    secret.deleted_at = datetime.now(timezone.utc)
    secret.is_active = False
    await db.flush()
