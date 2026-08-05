"""Lightweight in-process cron scheduler for scheduled workflow triggers.

Scans every ``SCHEDULER_INTERVAL_SECONDS`` for active workflows with
``trigger_type=schedule`` whose 5-field cron expression matches the current
minute, and fires them through the execution engine. Runs while the service
process is alive (single instance); a dedicated worker (Celery beat) can
replace it when scaling out. Guarded so a slow tick never blocks the API.
"""

import asyncio
from datetime import datetime, timezone

from app.core.db import FirestoreDB
from app.models.workflow import WorkflowStatus
from app.services import workflow_service
from app.services.execution_engine import run_workflow_execution, schedule as _schedule


def parse_cron_field(field: str, lo: int, hi: int) -> set[int]:
    """Parse one cron field (supports *, a-b, */n, a-b/n, a,b)."""
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        if part == "*":
            values.update(range(lo, hi + 1))
        elif "/" in part:
            base, _, step_s = part.partition("/")
            try:
                step = int(step_s)
            except ValueError:
                continue
            if base in ("*", ""):
                values.update(range(lo, hi + 1, step))
            elif "-" in base:
                a, b = base.split("-")
                values.update(range(int(a), int(b) + 1, step))
            else:
                values.update(range(int(base), hi + 1, step))
        elif "-" in part:
            a, b = part.split("-")
            values.update(range(int(a), int(b) + 1))
        else:
            try:
                values.add(int(part))
            except ValueError:
                continue
    return values


def cron_matches(expr: str, dt: datetime | None = None) -> bool:
    """True when a 5-field cron expression matches the given time (default: now UTC)."""
    if not expr:
        return False
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    minute, hour, dom, month, dow = parts
    dt = dt or datetime.now(timezone.utc)
    return (
        dt.minute in parse_cron_field(minute, 0, 59)
        and dt.hour in parse_cron_field(hour, 0, 23)
        and dt.day in parse_cron_field(dom, 1, 31)
        and dt.month in parse_cron_field(month, 1, 12)
        and dt.weekday() in parse_cron_field(dow, 0, 6)
    )


async def scheduler_tick(db: FirestoreDB) -> int:
    """Fire scheduled workflows whose cron matches this minute.

    Each workflow runs at most once per minute (tracked via
    ``last_scheduled_run``). Returns the number of executions started.
    """
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M")
    fired = 0

    for wf in db.query(workflow_service.WORKFLOWS):
        if wf.get("deleted_at") or wf.get("status") != WorkflowStatus.ACTIVE.value:
            continue
        if (wf.get("trigger_type") or "") != "schedule":
            continue
        cron = wf.get("schedule_cron") or ""
        if not cron or not cron_matches(cron, now):
            continue
        if (wf.get("last_scheduled_run") or "")[:16] >= stamp:
            continue  # already fired this minute

        # Mark as fired BEFORE creating the execution so a failure can't cause
        # a duplicate run on the next tick.
        wf["last_scheduled_run"] = now.isoformat()
        db.set(workflow_service.WORKFLOWS, wf["id"], wf)
        try:
            execution = await workflow_service.create_execution(
                db,
                wf,
                input_data={"trigger": "schedule", "cron": cron, "fired_at": now.isoformat()},
                triggered_by="scheduler",
            )
            execution = await workflow_service.start_execution(db, execution)
            _schedule(db, lambda: run_workflow_execution(db, str(execution["id"])))
            fired += 1
        except Exception:
            # A broken workflow shouldn't break the whole tick.
            continue

    return fired


async def run_scheduler(db: FirestoreDB, interval_seconds: int = 60) -> None:
    """Long-running scheduler loop; cancels cleanly with the parent task."""
    while True:
        try:
            await scheduler_tick(db)
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)
