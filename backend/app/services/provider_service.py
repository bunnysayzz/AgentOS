"""Provider config service - manage LLM API keys, test connections, encryption (Firestore)."""

import base64
from datetime import datetime, timezone

from app.core.db import AttrDict, FirestoreDB, new_id, now_iso
from app.schemas.mcp import ProviderConfigCreate
from app.core.config import settings

PROVIDER_CONFIGS = "provider_configs"


# ─── Simple XOR-based encryption (for development) ──
# In production, use HashiCorp Vault, AWS KMS, or similar.

def _encrypt_key(api_key: str) -> str:
    """Simple encryption for API keys using the app's encryption key."""
    key = settings.ENCRYPTION_KEY
    encrypted = []
    for i, c in enumerate(api_key):
        k = ord(key[i % len(key)])
        encrypted.append(chr(ord(c) ^ k))
    return base64.b64encode("".join(encrypted).encode()).decode()


def _decrypt_key(encrypted: str) -> str:
    """Decrypt an API key."""
    key = settings.ENCRYPTION_KEY
    decoded = base64.b64decode(encrypted.encode()).decode()
    decrypted = []
    for i, c in enumerate(decoded):
        k = ord(key[i % len(key)])
        decrypted.append(chr(ord(c) ^ k))
    return "".join(decrypted)


def _doc_id(provider) -> str:
    return provider.value if hasattr(provider, "value") else str(provider)


async def get_provider_config(db: FirestoreDB, provider) -> dict | None:
    """Get the config for a specific provider."""
    return db.get(PROVIDER_CONFIGS, _doc_id(provider))


async def list_provider_configs(db: FirestoreDB) -> list[dict]:
    """List all provider configs."""
    rows = db.query(PROVIDER_CONFIGS)
    rows.sort(key=lambda r: r.get("provider") or "")
    return rows


async def upsert_provider_config(db: FirestoreDB, config_in: ProviderConfigCreate) -> dict:
    """Create or update a provider config."""
    doc_id = _doc_id(config_in.provider)
    existing = db.get(PROVIDER_CONFIGS, doc_id)

    if existing:
        existing["encrypted_api_key"] = _encrypt_key(config_in.api_key)
        if config_in.base_url is not None:
            existing["base_url"] = config_in.base_url
        if config_in.default_model is not None:
            existing["default_model"] = config_in.default_model
        if config_in.config is not None:
            existing["config"] = config_in.config
        existing["is_active"] = True
        existing["last_error"] = None
    else:
        existing = AttrDict({
            "id": new_id(),
            "provider": _doc_id(config_in.provider),
            "encrypted_api_key": _encrypt_key(config_in.api_key),
            "base_url": config_in.base_url,
            "default_model": config_in.default_model,
            "config": config_in.config,
            "is_active": True,
            "last_tested_at": None,
            "last_error": None,
            "created_at": now_iso(),
        })

    db.set(PROVIDER_CONFIGS, doc_id, existing)
    return existing


async def delete_provider_config(db: FirestoreDB, provider) -> bool:
    """Delete a provider config."""
    doc_id = _doc_id(provider)
    if db.get(PROVIDER_CONFIGS, doc_id) is None:
        return False
    db.delete(PROVIDER_CONFIGS, doc_id)
    return True


async def test_connection(db: FirestoreDB, provider) -> tuple[bool, str]:
    """Test the connection to a provider by making a minimal API call."""
    from app.models.mcp import LLMProvider

    config = await get_provider_config(db, provider)
    if config is None:
        return False, "Provider not configured"

    api_key = _decrypt_key(config["encrypted_api_key"])
    base_url = config.get("base_url")

    import httpx

    async def _record(success: bool, error: str | None = None) -> tuple[bool, str]:
        config["last_tested_at"] = datetime.now(timezone.utc).isoformat()
        config["last_error"] = error
        db.set(PROVIDER_CONFIGS, _doc_id(provider), config)
        return success, error or "Connection successful"

    try:
        if provider == LLMProvider.OPENAI:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            url = base_url or "https://api.openai.com/v1/models"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=headers)
                if r.status_code == 200:
                    return await _record(True)
                error = r.json().get("error", {}).get("message", str(r.status_code))
                return await _record(False, error)

        elif provider == LLMProvider.ANTHROPIC:
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            url = base_url or "https://api.anthropic.com/v1/messages"
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
                    return await _record(True)
                error = r.json().get("error", {}).get("message", str(r.status_code))
                return await _record(False, error)

        elif provider == LLMProvider.GOOGLE:
            url = base_url or f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    return await _record(True)
                error = r.json().get("error", {}).get("message", str(r.status_code))
                return await _record(False, error)

        elif provider == LLMProvider.OLLAMA:
            url = base_url or "http://localhost:11434/api/tags"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    return await _record(True)
                return await _record(False, f"HTTP {r.status_code}")

        else:
            return False, f"Testing for {provider.value} is not yet supported"

    except Exception as e:
        return await _record(False, str(e))


def get_api_key_for_provider(provider_config: dict | None) -> str | None:
    """Get the decrypted API key for a provider config."""
    if provider_config is None:
        return None
    return _decrypt_key(provider_config["encrypted_api_key"])
