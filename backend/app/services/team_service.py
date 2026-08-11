"""Team management service — invites, RBAC, activity feed."""

from datetime import datetime, timezone
from app.core.db import FirestoreDB, new_id, now_iso

WORKSPACE_MEMBERS = "workspace_members"
TEAM_INVITES = "team_invites"
ACTIVITY_LOG = "activity_log"


# ─── Invite Management ───────────────────────────────

def create_invite(
    db: FirestoreDB,
    workspace_id: str,
    email: str,
    role: str = "member",
    invited_by: str | None = None,
) -> dict:
    """Create a team invitation."""
    # Check if user already has a pending invite
    for row in db.query(TEAM_INVITES, "email", email):
        if row.get("workspace_id") == workspace_id and row.get("status") == "pending":
            return row
    
    invite = {
        "id": new_id(),
        "workspace_id": workspace_id,
        "email": email,
        "role": role,
        "invited_by": invited_by,
        "status": "pending",
        "created_at": now_iso(),
        "expires_at": None,  # 7 days from now
    }
    db.add(TEAM_INVITES, invite)
    
    # Log activity
    log_activity(db, workspace_id, "invite_sent", invited_by, f"Invited {email} as {role}")
    
    return invite


def list_invites(db: FirestoreDB, workspace_id: str) -> list[dict]:
    """List all pending invitations for a workspace."""
    rows = db.query(TEAM_INVITES, "workspace_id", workspace_id)
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return [r for r in rows if r.get("status") == "pending"]


def accept_invite(db: FirestoreDB, invite_id: str, user_id: str) -> dict:
    """Accept a team invitation."""
    invite = db.get(TEAM_INVITES, invite_id)
    if not invite or invite.get("status") != "pending":
        from app.services.workspace_service import WorkspaceError
        raise WorkspaceError("Invite not found or already used", status_code=404)
    
    # Create membership
    membership = {
        "id": new_id(),
        "workspace_id": invite["workspace_id"],
        "user_id": user_id,
        "role": invite.get("role", "member"),
        "created_at": now_iso(),
    }
    db.add(WORKSPACE_MEMBERS, membership)
    
    # Update invite status
    invite["status"] = "accepted"
    db.set(TEAM_INVITES, invite_id, invite)
    
    # Log activity
    log_activity(db, invite["workspace_id"], "member_joined", user_id, f"Accepted invite")
    
    return membership


def cancel_invite(db: FirestoreDB, invite_id: str) -> None:
    """Cancel a pending invitation."""
    invite = db.get(TEAM_INVITES, invite_id)
    if invite:
        invite["status"] = "cancelled"
        db.set(TEAM_INVITES, invite_id, invite)


# ─── Role Management ─────────────────────────────────

async def update_member_role(
    db: FirestoreDB,
    workspace_id: str,
    user_id: str,
    new_role: str,
    updated_by: str | None = None,
) -> dict:
    """Update a member's role in a workspace."""
    # Find the membership
    for row in db.query(WORKSPACE_MEMBERS, "workspace_id", workspace_id):
        if str(row.get("user_id")) == str(user_id):
            old_role = row.get("role")
            row["role"] = new_role
            db.set(WORKSPACE_MEMBERS, row["id"], row)
            
            # Log activity
            log_activity(db, workspace_id, "role_changed", updated_by, 
                        f"Changed role from {old_role} to {new_role}")
            
            return row
    
    from app.services.workspace_service import MembershipNotFoundError
    raise MembershipNotFoundError()


def get_member_permissions(role: str) -> dict:
    """Get permissions for a role."""
    permissions = {
        "owner": {
            "manage_workspace": True,
            "manage_members": True,
            "manage_billing": True,
            "create_agents": True,
            "delete_agents": True,
            "run_workflows": True,
            "manage_providers": True,
            "view_telemetry": True,
            "manage_api_keys": True,
        },
        "admin": {
            "manage_workspace": False,
            "manage_members": True,
            "manage_billing": False,
            "create_agents": True,
            "delete_agents": True,
            "run_workflows": True,
            "manage_providers": True,
            "view_telemetry": True,
            "manage_api_keys": True,
        },
        "member": {
            "manage_workspace": False,
            "manage_members": False,
            "manage_billing": False,
            "create_agents": True,
            "delete_agents": False,
            "run_workflows": True,
            "manage_providers": False,
            "view_telemetry": True,
            "manage_api_keys": False,
        },
        "viewer": {
            "manage_workspace": False,
            "manage_members": False,
            "manage_billing": False,
            "create_agents": False,
            "delete_agents": False,
            "run_workflows": False,
            "manage_providers": False,
            "view_telemetry": True,
            "manage_api_keys": False,
        },
    }
    return permissions.get(role, permissions["viewer"])


# ─── Activity Feed ───────────────────────────────────

def log_activity(
    db: FirestoreDB,
    workspace_id: str,
    action: str,
    user_id: str | None = None,
    details: str | None = None,
) -> dict:
    """Log an activity event."""
    entry = {
        "id": new_id(),
        "workspace_id": workspace_id,
        "action": action,
        "user_id": user_id,
        "details": details,
        "created_at": now_iso(),
    }
    db.add(ACTIVITY_LOG, entry)
    return entry


def get_activity_feed(
    db: FirestoreDB,
    workspace_id: str,
    limit: int = 50,
) -> list[dict]:
    """Get recent activity for a workspace."""
    rows = db.query(ACTIVITY_LOG, "workspace_id", workspace_id)
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[:limit]


def get_activity_stats(db: FirestoreDB, workspace_id: str) -> dict:
    """Get activity statistics for a workspace."""
    rows = db.query(ACTIVITY_LOG, "workspace_id", workspace_id)
    
    actions = {}
    for row in rows:
        action = row.get("action", "unknown")
        actions[action] = actions.get(action, 0) + 1
    
    return {
        "total_events": len(rows),
        "by_action": actions,
    }
