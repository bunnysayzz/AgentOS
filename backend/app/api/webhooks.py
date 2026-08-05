"""Inbound webhook triggers for workflows.

External systems fire webhook-triggered workflows by POSTing to
``/api/v1/webhooks/{token}`` — the token is generated per workflow and IS the
secret (no user session required, which is what lets GitHub, Stripe, cron
services etc. call it). The request body becomes the execution's input_data.
"""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.core.database import get_db
from app.core.db import FirestoreDB
from app.services import workflow_service

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/{token}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_webhook(
    token: str,
    payload: Any = Body(default=None),
    db: FirestoreDB = Depends(get_db),
):
    """Fire a webhook-triggered workflow. Returns 202 with the execution id."""
    workflow = await workflow_service.find_workflow_by_webhook_token(db, token)
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    try:
        execution = await workflow_service.create_execution(
            db,
            workflow,
            input_data=payload if isinstance(payload, dict) else {"payload": payload},
            triggered_by="webhook",
        )
        execution = await workflow_service.start_execution(db, execution)

        from app.services.execution_engine import run_workflow_execution, schedule
        schedule(db, lambda: run_workflow_execution(db, str(execution["id"])))

        return {
            "status": "accepted",
            "execution_id": execution["id"],
            "workflow_id": workflow["id"],
            "workflow_name": workflow.get("name"),
        }
    except workflow_service.WorkflowError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
