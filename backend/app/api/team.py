"""Team management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, EmailStr

from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404
from app.core.db import FirestoreDB
from app.core.database import get_db
from app.services import team_service

router = APIRouter(prefix="/workspaces/{workspace_id}/team", tags=["team"])


# ─── Schemas ─────────────────────────────────────────

class InviteCreate(BaseModel):
    email: EmailStr
    role: str = Field("member", pattern="^(owner|admin|member|viewer)$")


class RoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(owner|admin|member|viewer)$")


class InviteAccept(BaseModel):
    invite_id: str


# ─── Invitations ─────────────────────────────────────

@router.get("/invites")
async def list_invites(
    workspace_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """List pending invitations for a workspace."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return team_service.list_invites(db, workspace["id"])


@router.post("/invites")
async def create_invite(
    workspace_id: str,
    invite_in: InviteCreate,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Create a team invitation (Admin+ only)."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    
    # Check permissions
    from app.services.workspace_service import get_workspace_membership
    membership = await get_workspace_membership(db, current_user["id"], workspace["id"])
    if not membership or membership.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can invite members")
    
    return team_service.create_invite(
        db, workspace["id"],
        email=invite_in.email,
        role=invite_in.role,
        invited_by=current_user["id"],
    )


@router.post("/invites/{invite_id}/cancel")
async def cancel_invite(
    workspace_id: str,
    invite_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Cancel a pending invitation."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    team_service.cancel_invite(db, invite_id)
    return {"status": "cancelled"}


@router.post("/invites/accept")
async def accept_invite(
    workspace_id: str,
    accept_in: InviteAccept,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Accept a team invitation."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return team_service.accept_invite(db, accept_in.invite_id, current_user["id"])


# ─── Members ─────────────────────────────────────────

@router.get("/members/{user_id}/role")
async def get_member_permissions(
    workspace_id: str,
    user_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get permissions for a member."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    
    from app.services.workspace_service import get_workspace_membership
    membership = await get_workspace_membership(db, user_id, workspace["id"])
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")
    
    return {
        "user_id": user_id,
        "role": membership.get("role"),
        "permissions": team_service.get_member_permissions(membership.get("role", "viewer")),
    }


@router.patch("/members/{user_id}/role")
async def update_member_role(
    workspace_id: str,
    user_id: str,
    role_in: RoleUpdate,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Update a member's role (Admin+ only)."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    
    from app.services.workspace_service import get_workspace_membership
    membership = await get_workspace_membership(db, current_user["id"], workspace["id"])
    if not membership or membership.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can change roles")
    
    return await team_service.update_member_role(
        db, workspace["id"], user_id, role_in.role, current_user["id"]
    )


# ─── Activity Feed ───────────────────────────────────

@router.get("/activity")
async def get_activity_feed(
    workspace_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get recent activity for a workspace."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return team_service.get_activity_feed(db, workspace["id"], limit)


@router.get("/activity/stats")
async def get_activity_stats(
    workspace_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get activity statistics for a workspace."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return team_service.get_activity_stats(db, workspace["id"])
