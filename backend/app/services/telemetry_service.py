"""Telemetry & Observability service — events, audit logs, stats (Firestore)."""

from datetime import datetime, timedelta, timezone

from app.core.db import FirestoreDB, stamp
from app.schemas.telemetry import TelemetryEventCreate

EVENTS = "telemetry_events"
AUDIT = "audit_logs"


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
    db: FirestoreDB,
    workspace_id: str | None,
    event_in: TelemetryEventCreate,
    execution_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Record a telemetry event."""
    event = stamp({
        "workspace_id": str(workspace_id) if workspace_id else None,
        "execution_id": str(execution_id) if execution_id else None,
        "event_name": event_in.event_name,
        "event_type": event_in.event_type,
        "severity": event_in.severity.value,
        "attributes": event_in.attributes,
        "body": event_in.body,
        "duration_ms": event_in.duration_ms,
        "error_message": event_in.error_message,
        "cost_usd": event_in.cost_usd,
        "trace_id": event_in.trace_id,
        "span_id": event_in.span_id,
    })
    db.add(EVENTS, event)
    return event


async def get_event_by_id(db: FirestoreDB, event_id: str) -> dict | None:
    return db.get(EVENTS, str(event_id))


async def list_events(
    db: FirestoreDB,
    workspace_id: str | None = None,
    event_type: str | None = None,
    severity=None,
    execution_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List telemetry events with optional filters."""
    rows = db.query(EVENTS) if workspace_id is None else db.query(EVENTS, "workspace_id", str(workspace_id))

    if event_type is not None:
        rows = [r for r in rows if r.get("event_type") == event_type]
    if severity is not None:
        sv = severity.value if hasattr(severity, "value") else severity
        rows = [r for r in rows if r.get("severity") == sv]
    if execution_id is not None:
        rows = [r for r in rows if str(r.get("execution_id") or "") == str(execution_id)]

    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[offset : offset + limit], len(rows)


# ─── Audit Logs ──────────────────────────────────────


async def create_audit_log(
    db: FirestoreDB,
    workspace_id: str | None,
    user_id: str | None,
    action,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    """Record an audit log entry."""
    log = stamp({
        "workspace_id": str(workspace_id) if workspace_id else None,
        "user_id": str(user_id) if user_id else None,
        "action": action.value if hasattr(action, "value") else str(action),
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "ip_address": ip_address,
        "user_agent": user_agent,
    })
    db.add(AUDIT, log)
    return log


async def list_audit_logs(
    db: FirestoreDB,
    workspace_id: str | None = None,
    user_id: str | None = None,
    action=None,
    resource_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List audit logs with optional filters."""
    rows = db.query(AUDIT) if workspace_id is None else db.query(AUDIT, "workspace_id", str(workspace_id))

    if user_id is not None:
        rows = [r for r in rows if str(r.get("user_id") or "") == str(user_id)]
    if action is not None:
        av = action.value if hasattr(action, "value") else action
        rows = [r for r in rows if r.get("action") == av]
    if resource_type is not None:
        rows = [r for r in rows if r.get("resource_type") == resource_type]

    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[offset : offset + limit], len(rows)


# ─── Dashboard Stats ─────────────────────────────────


async def get_workspace_stats(db: FirestoreDB, workspace_id: str, days: int = 7) -> dict:
    """Get workspace dashboard statistics."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_iso = since.isoformat()

    rows = db.query(EVENTS, "workspace_id", str(workspace_id))
    rows = [r for r in rows if (r.get("created_at") or "") >= since_iso]

    event_counts: dict[str, int] = {}
    error_count = 0
    total_cost = 0.0
    durations = []
    for r in rows:
        etype = r.get("event_type") or "unknown"
        event_counts[etype] = event_counts.get(etype, 0) + 1
        if r.get("severity") in ("error", "critical"):
            error_count += 1
        total_cost += r.get("cost_usd") or 0
        if r.get("duration_ms") is not None:
            durations.append(r["duration_ms"])

    audit_rows = [r for r in db.query(AUDIT, "workspace_id", str(workspace_id))
                  if (r.get("created_at") or "") >= since_iso]
    audit_counts: dict[str, int] = {}
    for r in audit_rows:
        act = r.get("action") or "unknown"
        audit_counts[act] = audit_counts.get(act, 0) + 1

    return {
        "period_days": days,
        "total_events": sum(event_counts.values()),
        "errors": error_count,
        "total_cost_usd": round(total_cost, 6),
        "avg_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0.0,
        "events_by_type": event_counts,
        "audit_by_action": audit_counts,
    }
