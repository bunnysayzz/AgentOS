"""Secret schemas.

Note: Secret values are write-only — they are never returned in API responses.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.secret import SecretProvider


class SecretCreate(BaseModel):
    name: str = Field(..., max_length=256)
    slug: str | None = Field(None, max_length=128, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    description: str | None = Field(None, max_length=2048)
    value: str = Field(..., min_length=1)  # The secret value to encrypt
    provider: SecretProvider = SecretProvider.BUILTIN
    environment: str | None = Field(None, max_length=64)


class SecretUpdate(BaseModel):
    name: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=2048)
    value: str | None = Field(None, min_length=1)
    is_active: bool | None = None


class SecretResponse(BaseModel):
    """Secret response — never includes the actual value."""
    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    description: str | None
    provider: SecretProvider
    environment: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}
