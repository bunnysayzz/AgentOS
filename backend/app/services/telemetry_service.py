"""Telemetry & Observability service — events, audit logs, and dashboard stats."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import TelemetryEvent, AuditLog, EventSeverity, AuditAction
from app.schemas.telemetry import TelemetryEventCreate


# ─── Errors ──────────────────────────────────────────


class TelemetryError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class TelemetryEventNotFoundError(TelemetryError):
    def __init__(self):
        super().__init__("Telemetry event not found", status_code=404)


# ─── Telemetry Events ────────────────────────────────


async def create_event(
    db: AsyncSession,
    workspace_id: UUID | None,
    event_in: TelemetryEventCreate,
    execution_id: UUID | None = None,
    user_id: UUID | None = None,
) -> TelemetryEvent:
    """Record a telemetry event."""
    event = TelemetryEvent(
        workspace_id=workspace_id,
        execution_id=execution_id,
        event_name=event_in.event_name,
        event_type=event_in.event_type,
        severity=event_in.severity,
        attributes=event_in.attributes,
        body=event_in.body,
        duration_ms=event_in.duration_ms,
        error_message=event_in.error_message,
        cost_usd=event_in.cost_usd,
        trace_id=event_in.trace_id,
        span_id=event_in.span_id,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


async def get_event_by_id(db: AsyncSession, event_id: UUID) -> TelemetryEvent | None:
    result = await db.execute(
        select(TelemetryEvent).where(TelemetryEvent.id == event_id)
    )
    return result.scalar_one_or_none()


async def list_events(
    db: AsyncSession,
    workspace_id: UUID | None = None,
    event_type: str | None = None,
    severity: EventSeverity | None = None,
    execution_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[TelemetryEvent], int]:
    """List telemetry events with optional filters."""
    conditions = []

    if workspace_id is not None:
        conditions.append(TelemetryEvent.workspace_id == workspace_id)
    if event_type is not None:
        conditions.append(TelemetryEvent.event_type == event_type)
    if severity is not None:
        conditions.append(TelemetryEvent.severity == severity)
    if execution_id is not None:
        conditions.append(TelemetryEvent.execution_id == execution_id)

    count_result = await db.execute(
        select(func.count(TelemetryEvent.id)).where(*conditions)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(TelemetryEvent)
        .where(*conditions)
        .order_by(TelemetryEvent.created_at.desc())
        .offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


# ─── Audit Logs ──────────────────────────────────────


async def create_audit_log(
    db: AsyncSession,
    workspace_id: UUID | None,
    user_id: UUID | None,
    action: AuditAction,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Record an audit log entry."""
    log = AuditLog(
        workspace_id=workspace_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    await db.flush()
    await db.refresh(log)
    return log


async def list_audit_logs(
    db: AsyncSession,
    workspace_id: UUID | None = None,
    user_id: UUID | None = None,
    action: AuditAction | None = None,
    resource_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    """List audit logs with optional filters."""
    conditions = []

    if workspace_id is not None:
        conditions.append(AuditLog.workspace_id == workspace_id)
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    if action is not None:
        conditions.append(AuditLog.action == action)
    if resource_type is not None:
        conditions.append(AuditLog.resource_type == resource_type)

    count_result = await db.execute(
        select(func.count(AuditLog.id)).where(*conditions)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc())
        .offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


# ─── Dashboard Stats ─────────────────────────────────


async def get_workspace_stats(
    db: AsyncSession, workspace_id: UUID, days: int = 7
) -> dict:
    """Get workspace dashboard statistics."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Event counts by type
    event_counts_result = await db.execute(
        select(
            TelemetryEvent.event_type,
            func.count(TelemetryEvent.id).label("count"),
        )
        .where(
            TelemetryEvent.workspace_id == workspace_id,
            TelemetryEvent.created_at >= since,
        )
        .group_by(TelemetryEvent.event_type)
    )
    event_counts = {row.event_type: row.count for row in event_counts_result.all()}

    # Error/warning counts
    error_result = await db.execute(
        select(func.count(TelemetryEvent.id))
        .where(
            TelemetryEvent.workspace_id == workspace_id,
            TelemetryEvent.severity.in_([EventSeverity.ERROR, EventSeverity.CRITICAL]),
            TelemetryEvent.created_at >= since,
        )
    )
    error_count = error_result.scalar() or 0

    # Total cost
    cost_result = await db.execute(
        select(func.coalesce(func.sum(TelemetryEvent.cost_usd), 0.0))
        .where(
            TelemetryEvent.workspace_id == workspace_id,
            TelemetryEvent.created_at >= since,
        )
    )
    total_cost = round(float(cost_result.scalar() or 0.0), 6)

    # Avg duration
    duration_result = await db.execute(
        select(func.coalesce(func.avg(TelemetryEvent.duration_ms), 0.0))
        .where(
            TelemetryEvent.workspace_id == workspace_id,
            TelemetryEvent.created_at >= since,
            TelemetryEvent.duration_ms.isnot(None),
        )
    )
    avg_duration = round(float(duration_result.scalar() or 0.0), 2)

    # Audit log counts by action
    audit_counts_result = await db.execute(
        select(
            AuditLog.action,
            func.count(AuditLog.id).label("count"),
        )
        .where(
            AuditLog.workspace_id == workspace_id,
            AuditLog.created_at >= since,
        )
        .group_by(AuditLog.action)
    )
    audit_counts = {row.action.value: row.count for row in audit_counts_result.all()}

    return {
        "period_days": days,
        "total_events": sum(event_counts.values()),
        "errors": error_count,
        "total_cost_usd": total_cost,
        "avg_duration_ms": avg_duration,
        "events_by_type": event_counts,
        "audit_by_action": audit_counts,
    }
