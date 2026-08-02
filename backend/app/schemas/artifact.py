"""Artifact schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class ArtifactCreate(BaseModel):
    name: str = Field(..., max_length=256)
    content_type: str = Field(..., max_length=128)
    metadata: dict | None = None


class ArtifactUpdate(BaseModel):
    name: str | None = Field(None, max_length=256)
    metadata: dict | None = None


class ArtifactResponse(BaseModel):
    id: UUID
    workspace_id: UUID | None
    name: str
    content_type: str
    size_bytes: int
    checksum: str | None
    artifact_metadata: dict | None = Field(None, alias="artifact_metadata")
    version: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True, "populate_by_name": True}
