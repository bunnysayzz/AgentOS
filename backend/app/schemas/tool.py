"""Tool schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.tool import ToolType, ToolAuthType


class ToolBase(BaseModel):
    name: str = Field(..., max_length=256)
    slug: str | None = Field(None, max_length=128, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(None, max_length=4096)
    tool_type: ToolType = ToolType.CUSTOM
    schema_definition: dict | None = None
    parameters: dict | None = None
    auth_type: ToolAuthType = ToolAuthType.NONE
    auth_config: dict | None = None
    is_public: bool = False
    tags: list[str] | None = None


class ToolCreate(ToolBase):
    source: str | None = Field(None, max_length=512)


class ToolUpdate(BaseModel):
    name: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=4096)
    schema_definition: dict | None = None
    parameters: dict | None = None
    auth_type: ToolAuthType | None = None
    auth_config: dict | None = None
    is_active: bool | None = None
    tags: list[str] | None = None


class ToolResponse(ToolBase):
    id: UUID
    workspace_id: UUID | None
    source: str | None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class ToolExecutionResponse(BaseModel):
    id: UUID
    tool_id: UUID
    execution_id: UUID | None
    status: str
    input_params: dict | None
    output_data: dict | None
    error_message: str | None
    duration_ms: int | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
