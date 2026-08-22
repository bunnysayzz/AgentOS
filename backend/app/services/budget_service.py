"""Budget & cost alert service — workspace-level spending limits and alerts (Firestore)."""

from datetime import datetime, timedelta, timezone

import httpx

from app.core.db import FirestoreDB
from app.services.mcp_service import LLM_CALLS

WORKSPACES = "workspaces"

# Key on the workspace budget settings that records which alert state was
# last delivered, so webhook notifications fire once per threshold crossing
# instead of on every check.
LAST_NOTIFIED_KEY = "_last_notified_state"


# ─── Budget Config ────────────────────────────────────

DEFAULT_BUDGET = {
    "monthly_limit_usd": None,       # None = unlimited
    "daily_limit_usd": None,
    "alert_threshold_pct": 80,       # alert when this % of budget is reached
    "hard_limit": False,             # if True, block calls when over budget
    "alert_emails": [],              # email addresses to notify
    "alert_webhook": None,           # optional webhook URL for alerts
}


def get_budget_settings(db: FirestoreDB, workspace_id: str) -> dict:
    """Get budget settings for a workspace."""
    ws = db.get(WORKSPACES, workspace_id)
    if not ws:
        return DEFAULT_BUDGET.copy()
    settings = ws.get("settings") or {}
    budget = settings.get("budget") or {}
    merged = DEFAULT_BUDGET.copy()
    merged.update(budget)
    return merged


def update_budget_settings(db: FirestoreDB, workspace_id: str, budget_in: dict) -> dict:
    """Update budget settings for a workspace."""
    ws = db.get(WORKSPACES, workspace_id)
    if not ws:
        from app.services.workspace_service import WorkspaceNotFoundError
        raise WorkspaceNotFoundError()
    settings = ws.get("settings") or {}
    current_budget = settings.get("budget") or {}
    updated_budget = {**DEFAULT_BUDGET, **current_budget, **budget_in}
    settings["budget"] = updated_budget
    ws["settings"] = settings
    db.set(WORKSPACES, workspace_id, ws)
    return updated_budget


# ─── Cost Tracking ────────────────────────────────────

def get_period_costs(db: FirestoreDB, workspace_id: str, period: str = "monthly") -> dict:
    """Get cost breakdown for a workspace."""
    now = datetime.now(timezone.utc)
    
    if period == "monthly":
        start_of_period = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_label = now.strftime("%Y-%m")
    elif period == "daily":
        start_of_period = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_label = now.strftime("%Y-%m-%d")
    else:
        start_of_period = now - timedelta(days=30)
        period_label = "30d"
    
    # Query the LLM-call ledger for this workspace in the period
    start_iso = start_of_period.isoformat()
    total_cost = 0.0
    total_calls = 0
    total_tokens = 0
    by_model = {}
    
    for call in db.query(LLM_CALLS, "workspace_id", workspace_id):
        call_time = call.get("created_at", "")
        if call_time and call_time >= start_iso:
            cost = call.get("cost_usd") or 0
            total_cost += cost
            total_calls += 1
            total_tokens += (call.get("prompt_tokens") or 0) + (call.get("completion_tokens") or 0)
            
            model = call.get("model_name", "unknown")
            provider = call.get("provider", "unknown")
            key = f"{provider}/{model}"
            if key not in by_model:
                by_model[key] = {"calls": 0, "tokens": 0, "cost_usd": 0.0}
            by_model[key]["calls"] += 1
            by_model[key]["tokens"] += (call.get("prompt_tokens") or 0) + (call.get("completion_tokens") or 0)
            by_model[key]["cost_usd"] += cost
    
    return {
        "period": period,
        "period_label": period_label,
        "start_date": start_iso,
        "total_cost_usd": round(total_cost, 6),
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "by_model": {k: {**v, "cost_usd": round(v["cost_usd"], 6)} for k, v in by_model.items()},
    }


def check_budget(db: FirestoreDB, workspace_id: str) -> dict:
    """Check if workspace is over/at budget. Returns status + details."""
    budget = get_budget_settings(db, workspace_id)
    monthly = get_period_costs(db, workspace_id, "monthly")
    daily = get_period_costs(db, workspace_id, "daily")
    
    alerts = []
    blocked = False
    
    # Monthly check
    if budget.get("monthly_limit_usd") is not None:
        limit = budget["monthly_limit_usd"]
        cost = monthly["total_cost_usd"]
        pct = (cost / limit * 100) if limit > 0 else (100 if cost > 0 else 0)
        if pct >= 100:
            alerts.append({"type": "monthly_exceeded", "limit": limit, "current": monthly["total_cost_usd"], "pct": round(pct, 1)})
            if budget.get("hard_limit"):
                blocked = True
        elif pct >= budget.get("alert_threshold_pct", 80):
            alerts.append({"type": "monthly_warning", "limit": limit, "current": monthly["total_cost_usd"], "pct": round(pct, 1)})
    
    # Daily check
    if budget.get("daily_limit_usd") is not None:
        limit = budget["daily_limit_usd"]
        cost = daily["total_cost_usd"]
        pct = (cost / limit * 100) if limit > 0 else (100 if cost > 0 else 0)
        if pct >= 100:
            alerts.append({"type": "daily_exceeded", "limit": limit, "current": daily["total_cost_usd"], "pct": round(pct, 1)})
            if budget.get("hard_limit"):
                blocked = True
        elif pct >= budget.get("alert_threshold_pct", 80):
            alerts.append({"type": "daily_warning", "limit": limit, "current": daily["total_cost_usd"], "pct": round(pct, 1)})
    
    return {
        "budget": budget,
        "monthly": monthly,
        "daily": daily,
        "alerts": alerts,
        "blocked": blocked,
    }


async def check_budget_and_notify(db: FirestoreDB, workspace_id: str) -> dict:
    """Check budget and deliver webhook alerts on newly crossed thresholds.

    Fires at most once per alert state (e.g. monthly_exceeded) until the
    state clears, so a dashboard page view or repeated checks don't spam the
    webhook. Email delivery (``alert_emails``) is not implemented — the app
    has no SMTP transport; webhook delivery covers machine notifications.
    """
    result = check_budget(db, workspace_id)

    ws = db.get(WORKSPACES, workspace_id)
    if ws is None:
        return result

    webhook = (result.get("budget") or {}).get("alert_webhook")
    if not webhook:
        return result

    state = ",".join(sorted(a["type"] for a in result.get("alerts", []))) or "ok"
    settings = ws.get("settings") or {}
    budget = settings.get("budget") or {}
    last_notified = budget.get(LAST_NOTIFIED_KEY)
    if state == last_notified:
        return result
    if state == "ok":
        # Healthy again — clear the notified marker so the next breach re-alerts.
        if last_notified and last_notified != "ok":
            budget[LAST_NOTIFIED_KEY] = "ok"
            settings["budget"] = budget
            ws["settings"] = settings
            db.set(WORKSPACES, workspace_id, ws)
        return result

    payload = {
        "event": "budget_alert",
        "workspace_id": workspace_id,
        "alerts": result.get("alerts", []),
        "blocked": result.get("blocked", False),
        "monthly": result.get("monthly", {}),
        "daily": result.get("daily", {}),
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(webhook, json=payload)
    except Exception:
        pass  # Alert delivery is best-effort; never break the budget page.

    budget[LAST_NOTIFIED_KEY] = state
    settings["budget"] = budget
    ws["settings"] = settings
    db.set(WORKSPACES, workspace_id, ws)
    return result
