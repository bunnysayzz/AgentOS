"""Workflow Engine API routes."""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404, require_workspace_role
from app.schemas.workflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse,
    WorkflowExecutionResponse,
)
from app.models.user import User
from app.models.workspace import Workspace, MembershipRole
from app.models.workflow import Workflow, WorkflowStatus
from app.services import workflow_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/workflows",
    tags=["Workflows"],
)


# ─── Dependency ─────────────────────────────────────


async def get_workflow_or_404(
    workflow_id: UUID,
    workspace: Workspace = Depends(get_workspace_or_404),
    db: AsyncSession = Depends(get_db),
) -> Workflow:
    wf = await workflow_service.get_workflow_by_id(db, workflow_id)
    if wf is None or wf.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return wf


# ─── Workflow CRUD ─────────────────────────────────


@router.get("", response_model=list[WorkflowResponse])
@router.get("/", response_model=list[WorkflowResponse])
async def list_workflows(
    workspace: Workspace = Depends(get_workspace_or_404),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    workflows, total = await workflow_service.list_workspace_workflows(
        db, workspace.id, page=page, page_size=page_size
    )
    return [WorkflowResponse.model_validate(w) for w in workflows]


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    wf_in: WorkflowCreate,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    try:
        wf = await workflow_service.create_workflow(db, workspace.id, wf_in)
        return WorkflowResponse.model_validate(wf)
    except workflow_service.InvalidDAGError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow: Workflow = Depends(get_workflow_or_404)):
    return WorkflowResponse.model_validate(workflow)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    wf_in: WorkflowUpdate,
    workflow: Workflow = Depends(get_workflow_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    try:
        wf = await workflow_service.update_workflow(db, workflow, wf_in)
        return WorkflowResponse.model_validate(wf)
    except workflow_service.InvalidDAGError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow: Workflow = Depends(get_workflow_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await workflow_service.delete_workflow(db, workflow)
    return None


# ─── Execution ─────────────────────────────────────


class WorkflowExecuteRequest(BaseModel):
    """Optional JSON body for workflow execution (empty body is allowed)."""

    input_data: dict | None = None


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    body: WorkflowExecuteRequest | None = Body(default=None),
    workflow: Workflow = Depends(get_workflow_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        execution = await workflow_service.create_execution(
            db,
            workflow,
            input_data=body.input_data if body else None,
            triggered_by=str(current_user.id),
        )
        return WorkflowExecutionResponse.model_validate(execution)
    except workflow_service.WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get("/{workflow_id}/executions", response_model=list[WorkflowExecutionResponse])
async def list_executions(
    workflow: Workflow = Depends(get_workflow_or_404),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    executions, total = await workflow_service.list_executions(
        db, workflow.id, page=page, page_size=page_size
    )
    return [WorkflowExecutionResponse.model_validate(e) for e in executions]


@router.get("/{workflow_id}/executions/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_execution(
    execution_id: UUID,
    workflow: Workflow = Depends(get_workflow_or_404),
    db: AsyncSession = Depends(get_db),
):
    execution = await workflow_service.get_execution(db, execution_id)
    if execution is None or execution.workflow_id != workflow.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return WorkflowExecutionResponse.model_validate(execution)


@router.post("/{workflow_id}/executions/{execution_id}/start", response_model=WorkflowExecutionResponse)
async def start_execution(
    execution_id: UUID,
    workflow: Workflow = Depends(get_workflow_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
    auto_run: bool = Query(True, description="Run the workflow DAG immediately in the background"),
):
    execution = await workflow_service.get_execution(db, execution_id)
    if execution is None or execution.workflow_id != workflow.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    try:
        execution = await workflow_service.start_execution(db, execution)
        if auto_run:
            from app.services.execution_engine import run_workflow_execution, schedule
            schedule(db, lambda: run_workflow_execution(db, str(execution["id"])))
        return WorkflowExecutionResponse.model_validate(execution)
    except workflow_service.WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/{workflow_id}/executions/{execution_id}/pause", response_model=WorkflowExecutionResponse)
async def pause_execution(
    execution_id: UUID,
    workflow: Workflow = Depends(get_workflow_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    execution = await workflow_service.get_execution(db, execution_id)
    if execution is None or execution.workflow_id != workflow.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    try:
        execution = await workflow_service.pause_execution(db, execution)
        return WorkflowExecutionResponse.model_validate(execution)
    except workflow_service.WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/{workflow_id}/executions/{execution_id}/resume", response_model=WorkflowExecutionResponse)
async def resume_execution(
    execution_id: UUID,
    workflow: Workflow = Depends(get_workflow_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    execution = await workflow_service.get_execution(db, execution_id)
    if execution is None or execution.workflow_id != workflow.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    try:
        execution = await workflow_service.resume_execution(db, execution)
        return WorkflowExecutionResponse.model_validate(execution)
    except workflow_service.WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/{workflow_id}/executions/{execution_id}/cancel", response_model=WorkflowExecutionResponse)
async def cancel_execution(
    execution_id: UUID,
    workflow: Workflow = Depends(get_workflow_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    execution = await workflow_service.get_execution(db, execution_id)
    if execution is None or execution.workflow_id != workflow.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    try:
        execution = await workflow_service.cancel_execution(db, execution)
        return WorkflowExecutionResponse.model_validate(execution)
    except workflow_service.WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/{workflow_id}/executions/{execution_id}/approve", response_model=WorkflowExecutionResponse)
async def approve_execution(
    execution_id: UUID,
    workflow: Workflow = Depends(get_workflow_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Approve a workflow execution that's waiting for approval (Admin+)."""
    execution = await workflow_service.get_execution(db, execution_id)
    if execution is None or execution.workflow_id != workflow.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    try:
        execution = await workflow_service.approve_execution(db, execution)
        # Resume the DAG from where it parked at the approval gate.
        from app.services.execution_engine import run_workflow_execution, schedule
        schedule(db, lambda: run_workflow_execution(db, str(execution["id"])))
        return WorkflowExecutionResponse.model_validate(execution)
    except workflow_service.WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
