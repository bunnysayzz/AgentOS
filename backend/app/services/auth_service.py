"""Auth service — Firebase-first user management over Firestore.

Passwords are handled entirely by Firebase Auth (never stored server-side).
Users are auto-created in Firestore on first authenticated request, and the
configured FIRST_SUPERUSER_EMAIL is promoted to superuser automatically.
"""

from typing import Any

from app.core.config import settings
from app.core.db import AttrDict, FirestoreDB, now_iso

USERS = "users"


class AuthError(Exception):
    """Base auth error."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class UserAlreadyExistsError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    def __init__(self):
        super().__init__("Invalid username or password", status_code=401)


class TokenExpiredError(AuthError):
    def __init__(self):
        super().__init__("Token has expired", status_code=401)


class UserNotFoundError(AuthError):
    def __init__(self):
        super().__init__("User not found", status_code=404)


def get_user_by_id(db: FirestoreDB, user_id: str) -> dict | None:
    """Get a user by their UUID (as stored in Firestore)."""
    user = db.get(USERS, str(user_id))
    if user is None or user.get("deleted_at"):
        return None
    return user


def get_user_by_email(db: FirestoreDB, email: str) -> dict | None:
    """Get a non-deleted user by email."""
    for row in db.query(USERS, "email", email):
        if not row.get("deleted_at"):
            return row
    return None


def get_user_by_username(db: FirestoreDB, username: str) -> dict | None:
    """Get a non-deleted user by username."""
    for row in db.query(USERS, "username", username):
        if not row.get("deleted_at"):
            return row
    return None


def _unique_username(db: FirestoreDB, base: str) -> str:
    """Return a username that doesn't collide with an existing user."""
    import re

    # UserResponse.username only allows [a-zA-Z0-9_-] — emails often contain
    # dots or other chars, so sanitize the base first.
    base = re.sub(r"[^a-zA-Z0-9_-]", "_", base)
    candidate = base[:64] or "user"
    counter = 1
    while get_user_by_username(db, candidate) is not None:
        suffix = f"_{counter}"
        candidate = f"{base[: 64 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def get_or_create_user_from_firebase(db: FirestoreDB, fb: dict) -> dict:
    """Find a user by Firebase email (or create them) and refresh login info.

    ``fb`` is the decoded Firebase ID token payload: ``uid``, ``email``,
    ``name``, ``picture``. Returns the Firestore user document dict.
    """
    email = fb.get("email") or f"{fb.get('uid', 'user')}@agentos.studio"
    full_name = fb.get("name") or fb.get("email", "").split("@")[0]
    avatar_url = fb.get("picture")

    user = get_user_by_email(db, email)
    if user is not None:
        # Refresh profile details and login bookkeeping
        updates: dict[str, Any] = {"last_login_at": now_iso()}
        if avatar_url and not user.get("avatar_url"):
            updates["avatar_url"] = avatar_url
        if not user.get("full_name") and full_name:
            updates["full_name"] = full_name
        updates["is_verified"] = True
        updates["firebase_uid"] = fb.get("uid")
        user.update(updates)
        db.set(USERS, user["id"], user)
        return user

    username = _unique_username(db, (fb.get("email") or "").split("@")[0] or "user")
    user = AttrDict({
        "id": _new_user_id(db),
        "email": email,
        "username": username,
        "full_name": full_name,
        "avatar_url": avatar_url,
        "is_active": True,
        "is_superuser": bool(
            settings.FIRST_SUPERUSER_EMAIL
            and email.lower() == settings.FIRST_SUPERUSER_EMAIL.lower()
        ),
        "is_verified": True,
        "last_login_at": now_iso(),
        "failed_login_attempts": 0,
        "firebase_uid": fb.get("uid"),
    })
    db.add(USERS, user)
    return user


def _new_user_id(db: FirestoreDB) -> str:
    """Generate an unused UUID string for a user document."""
    import uuid

    while True:
        candidate = str(uuid.uuid4())
        if db.get(USERS, candidate) is None:
            return candidate


def update_user(db: FirestoreDB, user_id: str, updates: dict) -> dict | None:
    """Apply partial updates to a user document."""
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    user.update(updates)
    db.set(USERS, user["id"], user)
    return user


def list_users(db: FirestoreDB, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    """List non-deleted users (superuser only), newest first."""
    rows = [r for r in db.query(USERS) if not r.get("deleted_at")]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


def soft_delete_user(db: FirestoreDB, user_id: str) -> dict | None:
    """Soft-delete a user (deleted_at + is_active=False)."""
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    user["deleted_at"] = now_iso()
    user["is_active"] = False
    db.set(USERS, user["id"], user)
    return user
