"""API Key service — create, list, revoke, and validate API keys (Firestore)."""

import secrets
import hashlib
from datetime import datetime, timezone

from app.core.db import FirestoreDB, stamp
from app.schemas.user import ApiKeyCreate

API_KEYS = "api_keys"


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
    db: FirestoreDB, user_id: str, key_in: ApiKeyCreate
) -> tuple[dict, str]:
    """Create a new API key for a user. Returns (key_record, full_key)."""
    full_key, key_prefix, key_hash = generate_api_key()

    api_key = stamp({
        "user_id": str(user_id),
        "name": key_in.name,
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "scopes": ",".join(key_in.scopes) if key_in.scopes else None,
        "expires_at": key_in.expires_at.isoformat() if key_in.expires_at else None,
        "is_active": True,
        "last_used_at": None,
    })
    db.add(API_KEYS, api_key)
    return api_key, full_key


async def list_user_api_keys(db: FirestoreDB, user_id: str) -> list[dict]:
    """List all API keys for a user."""
    rows = [r for r in db.query(API_KEYS, "user_id", str(user_id)) if not r.get("deleted_at")]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


async def get_api_key_by_id(db: FirestoreDB, key_id: str, user_id: str) -> dict | None:
    """Get a specific API key by ID (scoped to user)."""
    api_key = db.get(API_KEYS, str(key_id))
    if api_key is None or str(api_key.get("user_id") or "") != str(user_id):
        return None
    return api_key


def verify_api_key(db: FirestoreDB, full_key: str) -> dict | None:
    """Validate a full API key (sync — used by the MCP auth middleware).

    Returns the key record when the hash matches, the key is active and not
    expired; otherwise None. Bumps ``last_used_at`` on success.
    """
    if not full_key or not full_key.startswith("agos_"):
        return None

    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    for row in db.query(API_KEYS, "key_hash", key_hash):
        if not row.get("is_active"):
            continue
        expires = row.get("expires_at")
        if expires:
            try:
                if datetime.fromisoformat(expires.replace("Z", "+00:00")) < now:
                    continue
            except Exception:
                continue
        row["last_used_at"] = now.isoformat()
        db.set(API_KEYS, row["id"], row)
        return row
    return None


async def revoke_api_key(db: FirestoreDB, key_id: str, user_id: str) -> None:
    """Revoke (soft-delete) an API key."""
    api_key = await get_api_key_by_id(db, key_id, user_id)
    if api_key is None:
        raise ApiKeyNotFoundError()
    api_key["is_active"] = False
    db.set(API_KEYS, api_key["id"], api_key)


async def delete_api_key(db: FirestoreDB, key_id: str, user_id: str) -> None:
    """Permanently delete an API key."""
    api_key = await get_api_key_by_id(db, key_id, user_id)
    if api_key is None:
        raise ApiKeyNotFoundError()
    db.delete(API_KEYS, api_key["id"])
