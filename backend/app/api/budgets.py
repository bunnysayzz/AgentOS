"""Budget & cost alert API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404
from app.core.db import FirestoreDB
from app.core.database import get_db
from app.services import budget_service

router = APIRouter(prefix="/workspaces/{workspace_id}/budget", tags=["budgets"])


class BudgetUpdate(BaseModel):
    monthly_limit_usd: float | None = Field(None, ge=0, description="Monthly spending cap (null = unlimited)")
    daily_limit_usd: float | None = Field(None, ge=0, description="Daily spending cap (null = unlimited)")
    alert_threshold_pct: int = Field(80, ge=1, le=100, description="Alert at this % of budget")
    hard_limit: bool = Field(False, description="Block calls when budget exceeded")
    alert_emails: list[str] = Field(default_factory=list, description="Email addresses for alerts")
    alert_webhook: str | None = Field(None, description="Webhook URL for alerts")


@router.get("")
async def get_budget(
    workspace_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get budget settings and current usage for a workspace."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    result = budget_service.check_budget(db, workspace["id"])
    return result


@router.patch("")
async def update_budget(
    workspace_id: str,
    budget_in: BudgetUpdate,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Update budget settings for a workspace."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    # Only owner/admin can change budget
    from app.services.workspace_service import get_workspace_membership
    membership = await get_workspace_membership(db, current_user["id"], workspace["id"])
    if not membership or membership.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only workspace owners and admins can change budget settings")
    
    updated = budget_service.update_budget_settings(db, workspace["id"], budget_in.model_dump(exclude_unset=True))
    return updated


@router.get("/costs")
async def get_costs(
    workspace_id: str,
    period: str = "monthly",
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get cost breakdown for a workspace by period (monthly/daily/30d)."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return budget_service.get_period_costs(db, workspace["id"], period)
