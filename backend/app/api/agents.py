"""Agent API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404, require_workspace_role
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentExecutionCreate,
    AgentExecutionResponse,
)
from app.models.user import User
from app.models.workspace import Workspace, MembershipRole
from app.models.agent import Agent, AgentExecution, AgentStatus, ExecutionStatus
from app.services import agent_service

router = APIRouter(prefix="/workspaces/{workspace_id}/agents", tags=["Agents"])


# ─── Dependency ─────────────────────────────────────


async def get_agent_or_404(
    agent_id: UUID,
    workspace: Workspace = Depends(get_workspace_or_404),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """Get an agent and verify it belongs to the workspace."""
    agent = await agent_service.get_agent_by_id(db, agent_id)
    if agent is None or agent.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


# ─── Agent CRUD ─────────────────────────────────────


@router.get("", response_model=list[AgentResponse])
@router.get("/", response_model=list[AgentResponse])
async def list_agents(
    workspace: Workspace = Depends(get_workspace_or_404),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all agents in a workspace."""
    agents, total = await agent_service.list_workspace_agents(
        db, workspace.id, page=page, page_size=page_size
    )
    return [AgentResponse.model_validate(a) for a in agents]


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_in: AgentCreate,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new agent (Member+ required)."""
    agent = await agent_service.create_agent(db, workspace.id, agent_in)
    return AgentResponse.model_validate(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent: Agent = Depends(get_agent_or_404),
):
    """Get an agent by ID."""
    return AgentResponse.model_validate(agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_in: AgentUpdate,
    agent: Agent = Depends(get_agent_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    """Update an agent (Member+)."""
    agent = await agent_service.update_agent(db, agent, agent_in)
    return AgentResponse.model_validate(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent: Agent = Depends(get_agent_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Delete an agent (Admin+)."""
    await agent_service.delete_agent(db, agent)
    return None


# ─── Agent Execution ────────────────────────────────


@router.post("/{agent_id}/execute", response_model=AgentExecutionResponse, status_code=status.HTTP_201_CREATED)
async def execute_agent(
    exec_in: AgentExecutionCreate | None = None,
    agent: Agent = Depends(get_agent_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    """Execute an agent (creates a new execution)."""
    if agent.status != AgentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute agent in '{agent.status.value}' status. Set to 'active' first.",
        )

    execution = await agent_service.create_execution(db, agent.id, exec_in)
    return AgentExecutionResponse.model_validate(execution)


@router.get("/{agent_id}/executions", response_model=list[AgentExecutionResponse])
async def list_executions(
    agent: Agent = Depends(get_agent_or_404),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: ExecutionStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all executions for an agent."""
    executions, total = await agent_service.list_agent_executions(
        db, agent.id, page=page, page_size=page_size, status_filter=status_filter
    )
    return [AgentExecutionResponse.model_validate(e) for e in executions]


@router.get("/{agent_id}/executions/{execution_id}", response_model=AgentExecutionResponse)
async def get_execution(
    execution_id: UUID,
    agent: Agent = Depends(get_agent_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Get an execution by ID."""
    execution = await agent_service.get_execution_by_id(db, execution_id)
    if execution is None or execution.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return AgentExecutionResponse.model_validate(execution)


@router.post("/{agent_id}/executions/{execution_id}/start", response_model=AgentExecutionResponse)
async def start_execution(
    execution_id: UUID,
    agent: Agent = Depends(get_agent_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    """Start a pending execution."""
    execution = await agent_service.get_execution_by_id(db, execution_id)
    if execution is None or execution.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    try:
        execution = await agent_service.start_execution(db, execution)
        return AgentExecutionResponse.model_validate(execution)
    except agent_service.InvalidTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/{agent_id}/executions/{execution_id}/cancel", response_model=AgentExecutionResponse)
async def cancel_execution(
    execution_id: UUID,
    agent: Agent = Depends(get_agent_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running/paused execution."""
    execution = await agent_service.get_execution_by_id(db, execution_id)
    if execution is None or execution.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    try:
        execution = await agent_service.cancel_execution(db, execution)
        return AgentExecutionResponse.model_validate(execution)
    except agent_service.InvalidTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/{agent_id}/executions/{execution_id}/pause", response_model=AgentExecutionResponse)
async def pause_execution(
    execution_id: UUID,
    agent: Agent = Depends(get_agent_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    """Pause a running execution."""
    execution = await agent_service.get_execution_by_id(db, execution_id)
    if execution is None or execution.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    try:
        execution = await agent_service.pause_execution(db, execution)
        return AgentExecutionResponse.model_validate(execution)
    except agent_service.InvalidTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/{agent_id}/executions/{execution_id}/resume", response_model=AgentExecutionResponse)
async def resume_execution(
    execution_id: UUID,
    agent: Agent = Depends(get_agent_or_404),
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused execution."""
    execution = await agent_service.get_execution_by_id(db, execution_id)
    if execution is None or execution.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    try:
        execution = await agent_service.resume_execution(db, execution)
        return AgentExecutionResponse.model_validate(execution)
    except agent_service.InvalidTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


# ─── Sessions ───────────────────────────────────────


@router.get("/sessions/{session_id}/executions", response_model=list[AgentExecutionResponse])
async def list_session_executions(
    session_id: str,
    workspace: Workspace = Depends(get_workspace_or_404),
    db: AsyncSession = Depends(get_db),
):
    """List all executions in a session (scoped to workspace)."""
    executions = await agent_service.list_session_executions(
        db, session_id, workspace_id=workspace.id
    )
    return [AgentExecutionResponse.model_validate(e) for e in executions]
