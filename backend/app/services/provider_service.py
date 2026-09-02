"""Provider config service - manage LLM API keys, test connections, encryption (Firestore).

API keys are encrypted at rest with Fernet (AES-128-CBC + HMAC, key derived
from ``ENCRYPTION_KEY`` via PBKDF2) — the same scheme ``secret_service`` uses.
Legacy XOR-encrypted values (written before the Fernet migration) are still
decrypted transparently, so existing stored keys keep working.
"""

import base64
import threading
import time
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.db import AttrDict, FirestoreDB, new_id, now_iso
from app.core.config import settings
from app.schemas.mcp import ProviderConfigCreate

PROVIDER_CONFIGS = "provider_configs"

# ─── In-process TTL cache ──────────────────────────────────────────────
# Provider configs change rarely (an API-key upsert or delete), but are read
# 2-3 times per LLM call (fallback chain + preferred provider). Each read was
# a full Firestore collection scan — the single hottest repeated DB access in
# the gateway. Cache for 15s; invalidated on any write (upsert/delete/test).
_PROVIDER_CACHE_TTL_SECONDS = 15.0
_provider_cache: list[dict] | None = None
_provider_cache_ts = 0.0
_provider_cache_lock = threading.Lock()


def invalidate_provider_cache() -> None:
    """Drop the cached provider list (call after any provider write)."""
    global _provider_cache, _provider_cache_ts
    with _provider_cache_lock:
        _provider_cache = None
        _provider_cache_ts = 0.0

# Marker prefix for Fernet-encrypted values (legacy XOR values have none).
_FERNET_PREFIX = "fernet:"


def _get_fernet() -> Fernet:
    """Derive a Fernet key from ENCRYPTION_KEY (matches secret_service)."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"agentos-provider-config",
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.ENCRYPTION_KEY.encode()))
    return Fernet(key)


def _encrypt_key(api_key: str) -> str:
    """Encrypt an API key with Fernet (production-grade)."""
    return _FERNET_PREFIX + _get_fernet().encrypt(api_key.encode()).decode()


def _decrypt_key_legacy_xor(encrypted: str) -> str:
    """Decrypt a legacy XOR-encrypted key (pre-Fernet values only)."""
    key = settings.ENCRYPTION_KEY
    decoded = base64.b64decode(encrypted.encode()).decode()
    decrypted = []
    for i, c in enumerate(decoded):
        k = ord(key[i % len(key)])
        decrypted.append(chr(ord(c) ^ k))
    return "".join(decrypted)


def _decrypt_key(encrypted: str) -> str:
    """Decrypt an API key — Fernet values, falling back to legacy XOR."""
    if encrypted.startswith(_FERNET_PREFIX):
        return _get_fernet().decrypt(encrypted[len(_FERNET_PREFIX):].encode()).decode()
    return _decrypt_key_legacy_xor(encrypted)


def _doc_id(provider) -> str:
    return provider.value if hasattr(provider, "value") else str(provider)


async def get_provider_config(db: FirestoreDB, provider) -> dict | None:
    """Get the config for a specific provider."""
    # Single-document get is already cheap (no scan) — read fresh, but mirror
    # the cached list's TTL semantics by seeding from cache when available.
    return db.get(PROVIDER_CONFIGS, _doc_id(provider))


async def list_provider_configs(db: FirestoreDB) -> list[dict]:
    """List all provider configs (15s in-process TTL cache)."""
    global _provider_cache, _provider_cache_ts
    now = time.monotonic()
    with _provider_cache_lock:
        if (
            _provider_cache is not None
            and (now - _provider_cache_ts) < _PROVIDER_CACHE_TTL_SECONDS
        ):
            return [dict(r) for r in _provider_cache]

    rows = db.query(PROVIDER_CONFIGS)
    rows.sort(key=lambda r: r.get("provider") or "")
    with _provider_cache_lock:
        _provider_cache = [dict(r) for r in rows]
        _provider_cache_ts = time.monotonic()
    return [dict(r) for r in rows]


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
    invalidate_provider_cache()
    return existing


async def delete_provider_config(db: FirestoreDB, provider) -> bool:
    """Delete a provider config."""
    doc_id = _doc_id(provider)
    if db.get(PROVIDER_CONFIGS, doc_id) is None:
        return False
    db.delete(PROVIDER_CONFIGS, doc_id)
    invalidate_provider_cache()
    return True


async def test_connection(db: FirestoreDB, provider) -> tuple[bool, str]:
    """Test the connection to a provider by making a minimal API call.

    Supports every provider the gateway can route to: OpenAI-compatible
    providers (OpenAI, Groq, Cerebras, OpenRouter, Mistral, DeepSeek, LLM API,
    Together, Fireworks, and friends) are tested with a lightweight GET to
    their ``/models`` endpoint; Anthropic and Google use their native health
    calls; Ollama checks the local tags endpoint.
    """
    from app.models.mcp import LLMProvider
    from app.services.provider_metadata import get_provider_metadata

    config = await get_provider_config(db, provider)
    if config is None:
        return False, "Provider not configured"

    api_key = _decrypt_key(config["encrypted_api_key"])
    base_url = config.get("base_url") or get_provider_metadata(provider).get("base_url") or ""

    import httpx

    async def _record(success: bool, error: str | None = None) -> tuple[bool, str]:
        config["last_tested_at"] = datetime.now(timezone.utc).isoformat()
        config["last_error"] = error
        db.set(PROVIDER_CONFIGS, _doc_id(provider), config)
        invalidate_provider_cache()
        return success, error or "Connection successful"

    # Native providers have their own API formats
    try:
        if provider == LLMProvider.ANTHROPIC:
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            url = (base_url or "https://api.anthropic.com").rstrip("/") + "/v1/messages"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    url,
                    headers=headers,
                    json={
                        "model": "claude-3-5-haiku-20241022",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                )
                if r.status_code in (200, 201):
                    return await _record(True)
                try:
                    error = r.json().get("error", {}).get("message", str(r.status_code))
                except Exception:
                    error = str(r.status_code)
                return await _record(False, error)

        elif provider == LLMProvider.GOOGLE:
            url = (base_url or f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}")
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    return await _record(True)
                try:
                    error = r.json().get("error", {}).get("message", str(r.status_code))
                except Exception:
                    error = str(r.status_code)
                return await _record(False, error)

        elif provider == LLMProvider.OLLAMA:
            url = (base_url or "http://localhost:11434").rstrip("/") + "/api/tags"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    return await _record(True)
                return await _record(False, f"HTTP {r.status_code}")

        else:
            # All other providers (172+ from models.dev) are OpenAI-compatible
            url = (base_url or "https://api.openai.com/v1").rstrip("/") + "/models"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=headers)
                if r.status_code == 200:
                    return await _record(True)
                try:
                    error = r.json().get("error", {}).get("message", str(r.status_code))
                except Exception:
                    error = str(r.status_code)
                return await _record(False, error)

    except Exception as e:
        return await _record(False, str(e))


def get_api_key_for_provider(provider_config: dict | None) -> str | None:
    """Get the decrypted API key for a provider config."""
    if provider_config is None:
        return None
    return _decrypt_key(provider_config["encrypted_api_key"])
