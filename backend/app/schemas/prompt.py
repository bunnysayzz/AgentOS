"""Prompt schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.prompt import PromptType


class PromptBase(BaseModel):
    name: str = Field(..., max_length=256)
    slug: str | None = Field(None, max_length=128)
    description: str | None = Field(None, max_length=4096)
    prompt_type: PromptType = PromptType.TEMPLATE
    is_public: bool = False
    tags: list[str] | None = None


class PromptCreate(PromptBase):
    initial_content: str = ""


class PromptUpdate(BaseModel):
    name: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=4096)
    is_public: bool | None = None
    tags: list[str] | None = None


class PromptResponse(PromptBase):
    id: UUID
    workspace_id: UUID | None
    current_version: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class PromptVersionCreate(BaseModel):
    content: str
    template_variables: list[str] | None = None
    commit_message: str | None = Field(None, max_length=512)


class PromptVersionResponse(BaseModel):
    id: UUID
    prompt_id: UUID
    version: int
    content: str
    template_variables: list[str] | None
    commit_message: str | None
    token_count: int | None
    char_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
