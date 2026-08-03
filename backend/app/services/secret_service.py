"""Secrets Manager service — encrypted storage, CRUD (Firestore-backed)."""

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings
from app.core.db import FirestoreDB, now_iso, stamp
from app.schemas.secret import SecretCreate, SecretUpdate

SECRETS = "secrets"


# ─── Encryption ────────────────────────────────────


def _get_fernet() -> Fernet:
    """Get a Fernet instance using the configured encryption key."""
    key = settings.ENCRYPTION_KEY.encode()
    salt = b"agentos_studio_salt"  # Fixed salt for deterministic key
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    fernet_key = base64.urlsafe_b64encode(kdf.derive(key))
    return Fernet(fernet_key)


def encrypt_value(value: str) -> str:
    """Encrypt a secret value."""
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Decrypt a secret value."""
    return _get_fernet().decrypt(encrypted.encode()).decode()


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


async def create_secret(db: FirestoreDB, workspace_id: str, secret_in: SecretCreate) -> dict:
    """Create a new secret (value is encrypted before storage)."""
    slug = secret_in.slug
    if slug is None:
        slug = secret_in.name.lower().replace(" ", "_").replace("-", "_")
        slug = "".join(c for c in slug if c.isalnum() or c == "_")
        if not slug:
            slug = "secret"

    for row in db.query(SECRETS, "workspace_id", str(workspace_id)):
        if row.get("slug") == slug and not row.get("deleted_at"):
            raise SecretSlugTakenError()

    encrypted = encrypt_value(secret_in.value)
    secret = stamp({
        "workspace_id": str(workspace_id),
        "name": secret_in.name,
        "slug": slug,
        "description": secret_in.description,
        "encrypted_value": encrypted,
        "provider": secret_in.provider.value,
        "environment": secret_in.environment,
        "is_active": True,
    })
    db.add(SECRETS, secret)
    return secret


async def get_secret_by_id(db: FirestoreDB, secret_id: str) -> dict | None:
    secret = db.get(SECRETS, str(secret_id))
    if secret is None or secret.get("deleted_at"):
        return None
    return secret


async def get_secret_value(db: FirestoreDB, secret_id: str) -> str | None:
    """Get a secret's decrypted value (for internal use by other services)."""
    secret = await get_secret_by_id(db, secret_id)
    if secret is None or not secret.get("encrypted_value"):
        return None
    try:
        return decrypt_value(secret["encrypted_value"])
    except Exception:
        return None


async def list_workspace_secrets(
    db: FirestoreDB, workspace_id: str, page: int = 1, page_size: int = 50
) -> tuple[list[dict], int]:
    rows = [r for r in db.query(SECRETS, "workspace_id", str(workspace_id)) if not r.get("deleted_at")]
    rows.sort(key=lambda r: r.get("name") or "")
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def update_secret(db: FirestoreDB, secret: dict, secret_in: SecretUpdate) -> dict:
    """Update a secret. If value is provided, it's re-encrypted."""
    update_data = secret_in.model_dump(exclude_unset=True)

    if "value" in update_data:
        secret["encrypted_value"] = encrypt_value(update_data.pop("value"))

    for field, value in update_data.items():
        secret[field] = value

    db.set(SECRETS, secret["id"], secret)
    return secret


async def delete_secret(db: FirestoreDB, secret: dict) -> None:
    secret["deleted_at"] = now_iso()
    secret["is_active"] = False
    db.set(SECRETS, secret["id"], secret)
