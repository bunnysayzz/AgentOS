"""Workspace schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from app.models.workspace import MembershipRole


def _normalize_role(value) -> MembershipRole:
    """Accept role values case-insensitively ("MEMBER", "Member", "member")."""
    if isinstance(value, str):
        return value.strip().lower()
    return value


class WorkspaceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = Field(None, max_length=2048)


class WorkspaceCreate(WorkspaceBase):
    slug: str | None = Field(None, max_length=128, pattern=r"^[a-z0-9-]+$")


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=2048)
    settings: dict | None = None


class WorkspaceResponse(WorkspaceBase):
    id: UUID
    owner_id: UUID
    created_at: datetime
    updated_at: datetime | None
    member_count: int = 0
    slug: str = Field("", max_length=128)
    # Current user's role in this workspace ("owner"/"admin"/"member"/"viewer")
    role: str | None = None

    model_config = {"from_attributes": True}


class WorkspaceMemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    role: MembershipRole
    username: str = ""
    email: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceMemberAdd(BaseModel):
    user_id: UUID
    role: MembershipRole = MembershipRole.MEMBER

    @field_validator("role", mode="before")
    @classmethod
    def _role_case_insensitive(cls, value):
        return _normalize_role(value)


class WorkspaceMemberUpdate(BaseModel):
    role: MembershipRole

    @field_validator("role", mode="before")
    @classmethod
    def _role_case_insensitive(cls, value):
        return _normalize_role(value)
