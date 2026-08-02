"""Memory schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class MemoryEntryCreate(BaseModel):
    role: str = Field("user", max_length=32)
    content: str = Field(..., min_length=1)
    metadata: dict | None = None
    memory_type: str = Field("conversation", max_length=32)
    session_id: str | None = Field(None, max_length=128)


class MemorySearchQuery(BaseModel):
    query: str = Field(..., min_length=1)
    memory_type: str | None = None
    session_id: str | None = None
    agent_id: str | None = None
    limit: int = Field(10, ge=1, le=100)


class MemoryEntryResponse(BaseModel):
    id: UUID
    workspace_id: UUID | None
    agent_id: UUID | None
    session_id: str | None
    role: str
    content: str
    memory_type: str
    importance_score: float | None
    metadata: dict | None = Field(None, validation_alias="entry_metadata")
    created_at: datetime

    model_config = {"from_attributes": True}
