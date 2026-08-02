"""Authentication service - handles user registration, login, token management."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.user import UserCreate


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


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """Get a user by their UUID."""
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Get a user by their email."""
    result = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Get a user by their username."""
    result = await db.execute(
        select(User).where(User.username == username, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, user_in: UserCreate) -> User:
    """Register a new user."""
    # Check existing user (single query with OR)
    from sqlalchemy import or_
    result = await db.execute(
        select(User).where(
            or_(User.email == user_in.email, User.username == user_in.username),
            User.deleted_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.email == user_in.email:
            raise UserAlreadyExistsError("A user with this email already exists")
        raise UserAlreadyExistsError("A user with this username already exists")

    # Create user
    user = User(
        email=user_in.email,
        username=user_in.username,
        full_name=user_in.full_name,
        hashed_password=hash_password(user_in.password),
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    try:
        from app.services.firebase_db import firestore_db_service
        firestore_db_service.save_user(str(user.id), {
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
        })
    except Exception:
        pass

    return user


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User:
    """Authenticate a user by username/email and password."""
    # Try username first, then email
    user = await get_user_by_username(db, username)
    if user is None:
        user = await get_user_by_email(db, username)

    if user is None:
        raise InvalidCredentialsError()

    if not user.is_active:
        raise AuthError("User account is deactivated", status_code=403)

    if not verify_password(password, user.hashed_password):
        # Increment failed attempts
        user.failed_login_attempts += 1
        await db.flush()
        raise InvalidCredentialsError()

    # Reset failed attempts on success
    user.failed_login_attempts = 0
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    return user


async def login_user(db: AsyncSession, username: str, password: str) -> TokenResponse:
    """Authenticate and return tokens."""
    user = await authenticate_user(db, username, password)
    return await _create_tokens_for_user(user)


async def refresh_user_tokens(db: AsyncSession, refresh_token: str) -> TokenResponse:
    """Refresh tokens using a valid refresh token."""
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise TokenExpiredError()

    subject = payload.get("sub")
    if not subject:
        raise TokenExpiredError()

    try:
        user_id = UUID(subject)
    except ValueError:
        raise TokenExpiredError()

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise UserNotFoundError()

    return await _create_tokens_for_user(user)


async def _create_tokens_for_user(user: User) -> TokenResponse:
    """Create access and refresh tokens for a user."""
    return TokenResponse(
        access_token=create_access_token(subject=str(user.id)),
        refresh_token=create_refresh_token(subject=str(user.id)),
    )


async def authenticate_or_create_google_user(
    db: AsyncSession, email: str, full_name: str, avatar_url: str | None = None
) -> tuple[User, TokenResponse]:
    """Get existing user or create a new user account automatically for Google OAuth."""
    user = await get_user_by_email(db, email)
    if not user:
        base_username = email.split("@")[0]
        username = base_username
        count = 1
        while await get_user_by_username(db, username):
            username = f"{base_username}_{count}"
            count += 1

        user = User(
            email=email,
            username=username,
            full_name=full_name or username,
            avatar_url=avatar_url,
            hashed_password=hash_password(f"google_oauth_{email}"),
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
    else:
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url
        if full_name and not user.full_name:
            user.full_name = full_name
        user.is_verified = True

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    try:
        from app.services.firebase_db import firestore_db_service
        firestore_db_service.save_user(str(user.id), {
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
        })
    except Exception:
        pass

    tokens = await _create_tokens_for_user(user)
    return user, tokens
