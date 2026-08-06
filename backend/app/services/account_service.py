"""Account lifecycle service — GDPR/CCPA data export & deletion (Firestore).

``export_user_data`` returns a portable JSON snapshot of everything the user
owns or participates in. ``delete_user_data`` permanently removes it:

- workspaces the user OWNS → all domain data inside them (agents, workflows,
  tools, prompts, secrets, artifacts, memory, telemetry, executions, graph
  nodes, LLM calls) + memberships + the workspace itself
- workspaces the user only MEMBERS → their membership rows (the workspace
  and the other members' data stay untouched)
- the user's API keys and profile document

Provider configs are deployment-level singletons (no owner field) and are
intentionally not part of a single account's data.
"""

from datetime import datetime, timezone

from app.core.db import FirestoreDB, now_iso
from app.services import auth_service, workspace_service

USERS = "users"
MEMBERS = "workspace_members"
API_KEYS = "api_keys"

# ─── Collections scoped by workspace_id ─────────────────────────────────────
WORKSPACE_SCOPED = {
    "agents": "workspace_id",
    "workflows": "workspace_id",
    "tools": "workspace_id",
    "prompts": "workspace_id",
    "secrets": "workspace_id",
    "artifacts": "workspace_id",
    "memory_entries": "workspace_id",
    "telemetry_events": "workspace_id",
    "audit_logs": "workspace_id",
    "llm_calls": "workspace_id",
    "workspace_members": "workspace_id",
}

# ─── Collections scoped by a parent id (cascade deletes) ────────────────────
CHILD_SCOPED = {
    "agent_executions": "agent_id",
    "workflow_executions": "workflow_id",
    "tool_executions": "tool_id",
    "prompt_versions": "prompt_id",
    "execution_graph_nodes": "execution_id",
}


def _delete_many(db: FirestoreDB, coll: str, field: str, value: str) -> int:
    """Hard-delete every document in ``coll`` where field == value."""
    rows = db.query(coll, field, str(value))
    for row in rows:
        db.delete(coll, row["id"])
    return len(rows)


def _cascade_delete(db: FirestoreDB, coll: str, field: str, value: str) -> int:
    """Delete a collection's rows AND their child rows, recursively.

    ``CHILD_SCOPED`` maps child collections to the field referencing the
    parent row id (e.g. ``execution_graph_nodes.execution_id``). Each child
    row is itself deleted recursively, so nested chains like
    workflows → workflow_executions → execution_graph_nodes are fully
    purged — not just the first level.
    """
    rows = db.query(coll, field, str(value))
    for row in rows:
        for child_coll, child_field in CHILD_SCOPED.items():
            _cascade_delete(db, child_coll, child_field, row["id"])
        db.delete(coll, row["id"])
    return len(rows)


async def _workspace_snapshot(db: FirestoreDB, workspace: dict) -> dict:
    """Build a portable export snapshot for one workspace."""
    ws_id = workspace["id"]
    members = await workspace_service.list_members(db, workspace)

    snapshot: dict = {
        "workspace": {k: v for k, v in workspace.items() if k != "id"},
        "members": members,
        "collections": {},
    }

    for coll, field in WORKSPACE_SCOPED.items():
        rows = [dict(r) for r in db.query(coll, field, ws_id)]
        if coll == "secrets":
            # Decrypt values so the user keeps their own credentials.
            from app.services.secret_service import get_secret_value
            for row in rows:
                row.pop("encrypted_value", None)
                try:
                    row["value"] = await get_secret_value(db, row["id"])
                except Exception:
                    row["value"] = None
        snapshot["collections"][coll] = rows

    # Cascade child collections (executions, versions, graph nodes) per parent.
    for coll, field in WORKSPACE_SCOPED.items():
        if coll not in ("agents", "workflows", "tools", "prompts"):
            continue
        for row in db.query(coll, field, ws_id):
            parent_id = row["id"]
            for child_coll, child_field in CHILD_SCOPED.items():
                child_rows = [dict(c) for c in db.query(child_coll, child_field, parent_id)]
                if child_rows:
                    snapshot["collections"].setdefault(child_coll, []).extend(child_rows)
    return snapshot


async def export_user_data(db: FirestoreDB, user: dict) -> dict:
    """Return a portable JSON snapshot of all the user's data."""
    user_id = str(user["id"])
    export: dict = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "user": {k: v for k, v in user.items() if k != "id"},
    }

    # API keys
    api_keys = [dict(r) for r in db.query(API_KEYS, "user_id", user_id)]
    export["api_keys"] = api_keys

    # Workspaces (owned → full snapshot; member-only → membership info)
    member_rows = db.query(MEMBERS, "user_id", user_id)
    workspaces: list[dict] = []
    for m in member_rows:
        ws = await workspace_service.get_workspace_by_id(db, m["workspace_id"])
        if ws is None:
            continue
        if str(ws.get("owner_id")) == user_id:
            workspaces.append(await _workspace_snapshot(db, ws))
        else:
            workspaces.append({
                "workspace": {k: v for k, v in ws.items() if k != "id"},
                "membership": dict(m),
            })
    export["workspaces"] = workspaces
    return export


async def delete_user_data(db: FirestoreDB, user: dict) -> dict:
    """Permanently delete all of a user's data. Returns a summary dict."""
    user_id = str(user["id"])
    summary: dict[str, int] = {}

    member_rows = db.query(MEMBERS, "user_id", user_id)
    owned_ws: list[str] = []
    member_only_ws: list[str] = []
    for m in member_rows:
        ws = await workspace_service.get_workspace_by_id(db, m["workspace_id"])
        if ws is None:
            continue
        if str(ws.get("owner_id")) == user_id:
            owned_ws.append(ws["id"])
        else:
            member_only_ws.append(ws["id"])

    # Owned workspaces → delete everything inside.
    for ws_id in owned_ws:
        for coll, field in WORKSPACE_SCOPED.items():
            if coll == "workspace_members":
                summary["workspace_members"] = summary.get("workspace_members", 0) + _delete_many(db, coll, field, ws_id)
                continue
            summary[coll] = summary.get(coll, 0) + _cascade_delete(db, coll, field, ws_id)
        ws_doc = db.get("workspaces", ws_id)
        if ws_doc is not None:
            db.delete("workspaces", ws_id)
            summary["workspaces"] = summary.get("workspaces", 0) + 1

    # Member-only workspaces → just remove THIS user's membership row
    # (never the workspace or the other members' rows).
    for ws_id in member_only_ws:
        membership = await workspace_service.get_workspace_membership(db, user_id, ws_id)
        if membership is not None:
            db.delete(MEMBERS, membership["id"])
            summary["workspace_members"] = summary.get("workspace_members", 0) + 1

    # API keys + profile.
    summary["api_keys"] = _delete_many(db, API_KEYS, "user_id", user_id)
    auth_service.soft_delete_user(db, user_id)
    summary["users"] = 1
    return summary
