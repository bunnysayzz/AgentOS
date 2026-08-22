"""Telemetry & Observability API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import FirestoreDB
from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404
from app.schemas.telemetry import (
    TelemetryEventCreate,
    TelemetryEventResponse,
    AuditLogResponse,
)
from app.models.user import User
from app.models.workspace import Workspace
from app.models.telemetry import EventSeverity, AuditAction
from app.services import telemetry_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["Telemetry & Observability"],
)


# ─── Telemetry Events ────────────────────────────────


@router.post("/events", response_model=TelemetryEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_in: TelemetryEventCreate,
    workspace: Workspace = Depends(get_workspace_or_404),
    db: FirestoreDB = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Record a telemetry event."""
    event = await telemetry_service.create_event(
        db, workspace.id, event_in, user_id=current_user.id
    )
    return TelemetryEventResponse.model_validate(event)


@router.get("/events", response_model=list[TelemetryEventResponse])
async def list_events(
    workspace: Workspace = Depends(get_workspace_or_404),
    event_type: str | None = Query(None),
    severity: EventSeverity | None = Query(None),
    execution_id: UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: FirestoreDB = Depends(get_db),
):
    """List telemetry events with optional filters."""
    events, total = await telemetry_service.list_events(
        db,
        workspace_id=workspace.id,
        event_type=event_type,
        severity=severity,
        execution_id=execution_id,
        limit=limit,
        offset=offset,
    )
    return [TelemetryEventResponse.model_validate(e) for e in events]


@router.get("/events/stats")
async def get_event_stats(
    workspace: Workspace = Depends(get_workspace_or_404),
    days: int = Query(7, ge=1, le=90),
    db: FirestoreDB = Depends(get_db),
):
    """Get workspace dashboard statistics."""
    stats = await telemetry_service.get_workspace_stats(db, workspace.id, days=days)
    return stats


@router.get("/events/{event_id}", response_model=TelemetryEventResponse)
async def get_event(
    event_id: UUID,
    workspace: Workspace = Depends(get_workspace_or_404),
    db: FirestoreDB = Depends(get_db),
):
    """Get a specific telemetry event."""
    event = await telemetry_service.get_event_by_id(db, event_id)
    if event is None or event.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return TelemetryEventResponse.model_validate(event)


# ─── Audit Logs ──────────────────────────────────────


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    workspace: Workspace = Depends(get_workspace_or_404),
    action: AuditAction | None = Query(None),
    resource_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: FirestoreDB = Depends(get_db),
):
    """List audit logs for a workspace."""
    logs, total = await telemetry_service.list_audit_logs(
        db,
        workspace_id=workspace.id,
        action=action,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )
    return [AuditLogResponse.model_validate(l) for l in logs]
