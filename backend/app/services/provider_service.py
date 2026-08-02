"""Provider config service - manage LLM API keys, test connections, encryption."""

import os
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp import LLMProvider, ProviderConfig
from app.schemas.mcp import ProviderConfigCreate
from app.core.config import settings


# ─── Simple XOR-based encryption (for development) ──
# In production, use HashiCorp Vault, AWS KMS, or similar.

def _encrypt_key(api_key: str) -> str:
    """Simple encryption for API keys using the app's encryption key."""
    key = settings.ENCRYPTION_KEY
    encrypted = []
    for i, c in enumerate(api_key):
        k = ord(key[i % len(key)])
        encrypted.append(chr(ord(c) ^ k))
    # Encode to base85 for safe storage
    import base64
    return base64.b64encode("".join(encrypted).encode()).decode()


def _decrypt_key(encrypted: str) -> str:
    """Decrypt an API key."""
    import base64
    key = settings.ENCRYPTION_KEY
    decoded = base64.b64decode(encrypted.encode()).decode()
    decrypted = []
    for i, c in enumerate(decoded):
        k = ord(key[i % len(key)])
        decrypted.append(chr(ord(c) ^ k))
    return "".join(decrypted)


# ─── CRUD ──────────────────────────────────────────


async def get_provider_config(
    db: AsyncSession, provider: LLMProvider
) -> ProviderConfig | None:
    """Get the config for a specific provider."""
    result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.provider == provider)
    )
    return result.scalar_one_or_none()


async def list_provider_configs(
    db: AsyncSession,
) -> list[ProviderConfig]:
    """List all provider configs."""
    result = await db.execute(
        select(ProviderConfig).order_by(ProviderConfig.provider)
    )
    return list(result.scalars().all())


async def upsert_provider_config(
    db: AsyncSession, config_in: ProviderConfigCreate
) -> ProviderConfig:
    """Create or update a provider config."""
    existing = await get_provider_config(db, config_in.provider)

    if existing:
        existing.encrypted_api_key = _encrypt_key(config_in.api_key)
        if config_in.base_url is not None:
            existing.base_url = config_in.base_url
        if config_in.default_model is not None:
            existing.default_model = config_in.default_model
        if config_in.config is not None:
            existing.config = config_in.config
        existing.is_active = True
        existing.last_error = None
        existing.updated_at = datetime.now(timezone.utc)
    else:
        existing = ProviderConfig(
            provider=config_in.provider,
            encrypted_api_key=_encrypt_key(config_in.api_key),
            base_url=config_in.base_url,
            default_model=config_in.default_model,
            config=config_in.config,
            is_active=True,
        )
        db.add(existing)

    await db.flush()
    await db.refresh(existing)
    return existing


async def delete_provider_config(
    db: AsyncSession, provider: LLMProvider
) -> bool:
    """Delete a provider config."""
    config = await get_provider_config(db, provider)
    if config is None:
        return False
    await db.delete(config)
    await db.flush()
    return True


async def test_connection(
    db: AsyncSession, provider: LLMProvider
) -> tuple[bool, str]:
    """Test the connection to a provider by making a minimal API call."""
    config = await get_provider_config(db, provider)
    if config is None:
        return False, "Provider not configured"

    api_key = _decrypt_key(config.encrypted_api_key)
    base_url = config.base_url

    import httpx

    try:
        if provider == LLMProvider.OPENAI:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            url = base_url or "https://api.openai.com/v1/models"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=headers)
                if r.status_code == 200:
                    config.last_tested_at = datetime.now(timezone.utc)
                    config.last_error = None
                    await db.flush()
                    return True, "Connection successful"
                else:
                    error = r.json().get("error", {}).get("message", str(r.status_code))
                    config.last_error = error
                    await db.flush()
                    return False, error

        elif provider == LLMProvider.ANTHROPIC:
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            url = base_url or "https://api.anthropic.com/v1/messages"
            # Just check auth with a minimal request
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    url,
                    headers=headers,
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                )
                if r.status_code in (200, 201):
                    config.last_tested_at = datetime.now(timezone.utc)
                    config.last_error = None
                    await db.flush()
                    return True, "Connection successful"
                else:
                    error = r.json().get("error", {}).get("message", str(r.status_code))
                    config.last_error = error
                    await db.flush()
                    return False, error

        elif provider == LLMProvider.GOOGLE:
            url = base_url or f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    config.last_tested_at = datetime.now(timezone.utc)
                    config.last_error = None
                    await db.flush()
                    return True, "Connection successful"
                else:
                    error = r.json().get("error", {}).get("message", str(r.status_code))
                    config.last_error = error
                    await db.flush()
                    return False, error

        elif provider == LLMProvider.OLLAMA:
            url = base_url or "http://localhost:11434/api/tags"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    config.last_tested_at = datetime.now(timezone.utc)
                    config.last_error = None
                    await db.flush()
                    return True, "Connection successful"
                else:
                    config.last_error = str(r.status_code)
                    await db.flush()
                    return False, f"HTTP {r.status_code}"

        else:
            return False, f"Testing for {provider.value} is not yet supported"

    except Exception as e:
        config.last_error = str(e)
        await db.flush()
        return False, str(e)


def get_api_key_for_provider(
    provider_config: ProviderConfig | None,
) -> str | None:
    """Get the decrypted API key for a provider config."""
    if provider_config is None:
        return None
    return _decrypt_key(provider_config.encrypted_api_key)
