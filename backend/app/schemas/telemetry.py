"""Telemetry and audit log schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.telemetry import EventSeverity, AuditAction


class TelemetryEventCreate(BaseModel):
    event_name: str = Field(..., max_length=256)
    event_type: str = Field(..., max_length=64)
    severity: EventSeverity = EventSeverity.INFO
    attributes: dict | None = None
    body: str | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    cost_usd: float | None = None
    trace_id: str | None = Field(None, max_length=64)
    span_id: str | None = Field(None, max_length=64)


class TelemetryEventResponse(BaseModel):
    id: UUID
    event_name: str
    event_type: str
    severity: EventSeverity
    attributes: dict | None
    duration_ms: int | None
    error_message: str | None
    cost_usd: float | None
    trace_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    id: UUID
    workspace_id: UUID | None
    user_id: UUID | None
    action: AuditAction
    resource_type: str
    resource_id: str | None
    details: dict | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: list[dict]
    total: int
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
