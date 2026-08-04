"""User schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr, field_validator


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

    # Defense-in-depth: legacy Firestore docs may hold None where a bool is
    # expected. Coerce instead of failing validation (the service layer also
    # normalizes, this catches anything that slips through).
    @field_validator("is_active", "is_superuser", "is_verified", mode="before")
    @classmethod
    def _coerce_bool(cls, v):
        if v is None:
            return False
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)

    @field_validator("avatar_url", "full_name", mode="before")
    @classmethod
    def _clean_optional_str(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip().lower() in ("", "none", "null", "nan", "undefined"):
            return None
        return v


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
