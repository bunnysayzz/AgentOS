"""Dashboard API routes - aggregated stats in one request."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.api.deps import get_optional_user
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def dashboard_stats(
    workspace_id: UUID | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    db=Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """All dashboard numbers in one call.

    Replaces ~12 parallel list fetches the SPA used to fire. Guests (no
    token) receive a zeroed payload so the dashboard renders its onboarding
    state without touching any collections.
    """
    return await dashboard_service.get_dashboard_stats(
        db,
        user=current_user,
        workspace_id=str(workspace_id) if workspace_id else None,
        days=days,
    )
