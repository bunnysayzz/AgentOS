"""Webhook debugger API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404
from app.core.db import FirestoreDB
from app.core.database import get_db
from app.services import webhook_debugger

router = APIRouter(prefix="/workspaces/{workspace_id}/webhook-debugger", tags=["webhook-debugger"])


class WebhookTestRequest(BaseModel):
    url: str = Field(..., description="Target URL to test")
    method: str = Field("POST", description="HTTP method")
    headers: dict | None = Field(None, description="Request headers")
    body: str | None = Field(None, description="Request body (JSON string)")


@router.get("/logs")
async def list_logs(
    workspace_id: str,
    webhook_id: str | None = None,
    limit: int = 50,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """List webhook logs for a workspace."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return webhook_debugger.list_webhook_logs(db, workspace["id"], webhook_id, limit)


@router.get("/logs/{log_id}")
async def get_log(
    workspace_id: str,
    log_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get a specific webhook log entry."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    log = webhook_debugger.get_webhook_log(db, log_id)
    if not log or log.get("workspace_id") != workspace["id"]:
        raise HTTPException(status_code=404, detail="Log not found")
    return log


@router.post("/test")
async def test_webhook(
    workspace_id: str,
    test_in: WebhookTestRequest,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Send a test webhook and log the result."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return webhook_debugger.test_webhook(
        db, workspace["id"],
        url=test_in.url,
        method=test_in.method,
        headers=test_in.headers,
        body=test_in.body,
    )


@router.post("/retry/{log_id}")
async def retry_webhook(
    workspace_id: str,
    log_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Retry a webhook from a previous log entry."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return webhook_debugger.retry_webhook(db, log_id)
