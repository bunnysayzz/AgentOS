"""User schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr


# ─── User ─────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    full_name: str | None = Field(None, max_length=128)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(None, max_length=128)
    avatar_url: str | None = Field(None, max_length=512)


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    is_superuser: bool
    is_verified: bool
    avatar_url: str | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int


# ─── API Key ──────────────────────────────────────────────

class ApiKeyCreate(BaseModel):
    name: str = Field(..., max_length=128)
    scopes: list[str] | None = None
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    scopes: str | None
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Includes the full key value (only returned on creation)."""
    full_key: str


# ─── Password Change ────────────────────────────────────────

class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
