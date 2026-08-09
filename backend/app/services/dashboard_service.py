"""Dashboard stats service - one endpoint for all dashboard numbers.

The old dashboard fired ~12 separate list endpoints (workspaces, models,
recent calls, keys, providers + 7 workspace-scoped lists) just to display
counts. Each fetched entire collections and shipped them to the browser.

This service computes the same numbers server-side with aggregate ``count()``
queries and date-bounded scans, so a dashboard load touches Firestore a
handful of times instead of downloading every document in every collection.
"""

from datetime import datetime, timedelta, timezone

from app.core.db import FirestoreDB
from app.services import (
    api_key_service,
    mcp_service,
    provider_service,
    workspace_service,
)
from app.services.telemetry_service import EVENTS, AUDIT


async def get_dashboard_stats(
    db: FirestoreDB,
    user: dict | None,
    workspace_id: str | None = None,
    days: int = 30,
) -> dict:
    """Compute the full dashboard payload in one call.

    Guests (``user is None``) get zeroed stats — the page renders its
    guest/onboarding state without touching any collections.
    """
    if user is None:
        return _empty_stats()

    # ─── Global stats ────────────────────────────────────────────────────
    workspaces, _total = await workspace_service.list_user_workspaces(db, user)
    workspace_count = len(workspaces)

    model_count = len(await mcp_service.get_available_models(db))

    # LLM call usage over the window (date-bounded scan — never the full
    # collection). Fall back to recent calls when the collection is small.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    calls = db.query_since(mcp_service.LLM_CALLS, None, None, cutoff)
    call_count = len(calls)
    total_tokens = sum(r.get("total_tokens") or 0 for r in calls)
    total_cost = float(sum(r.get("cost_usd") or 0 for r in calls))

    key_count = len(await api_key_service.list_user_api_keys(db, user["id"]))

    provider_configs = await provider_service.list_provider_configs(db)
    configured_providers = sum(1 for c in provider_configs if c.get("is_active"))

    # ─── Workspace-scoped stats (first/selected workspace) ───────────────
    ws_id = workspace_id or (workspaces[0]["id"] if workspaces else None)
    ws_stats = await _workspace_stats(db, ws_id, days) if ws_id else None

    return {
        "workspaces": [
            {"id": w["id"], "name": w["name"], "role": w.get("role")}
            for w in workspaces
        ],
        "workspace_count": workspace_count,
        "model_count": model_count,
        "call_count": call_count,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "key_count": key_count,
        "configured_providers": configured_providers,
        "first_ws": ws_id,
        "workspace": ws_stats,
    }


async def _workspace_stats(
    db: FirestoreDB, ws_id: str, days: int
) -> dict | None:
    """Counts for one workspace (aggregate count queries + date-bounded)."""
    from app.services import agent_service, artifact_service, prompt_service, tool_service, workflow_service

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    return {
        "agent_count": db.count(agent_service.AGENTS, "workspace_id", str(ws_id)),
        "workflow_count": db.count(workflow_service.WORKFLOWS, "workspace_id", str(ws_id)),
        "prompt_count": db.count(prompt_service.PROMPTS, "workspace_id", str(ws_id)),
        "tool_count": db.count(tool_service.TOOLS, "workspace_id", str(ws_id)),
        "secret_count": db.count("secrets", "workspace_id", str(ws_id)),
        "artifact_count": db.count(artifact_service.ARTIFACTS, "workspace_id", str(ws_id)),
        "telemetry_events": db.count_since(EVENTS, "workspace_id", str(ws_id), since),
        "telemetry_errors": sum(
            1 for r in db.query_since(EVENTS, "workspace_id", str(ws_id), since)
            if r.get("severity") in ("error", "critical")
        ),
    }


def _empty_stats() -> dict:
    """Zeroed payload for guests / unauthenticated dashboard loads."""
    return {
        "workspaces": [],
        "workspace_count": 0,
        "model_count": 0,
        "call_count": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "key_count": 0,
        "configured_providers": 0,
        "first_ws": None,
        "workspace": None,
    }
