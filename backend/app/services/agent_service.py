"""Agent service - CRUD, execution lifecycle, state machine transitions."""

import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent, AgentExecution, AgentStatus, ExecutionStatus
from app.models.workspace import Workspace
from app.schemas.agent import AgentCreate, AgentUpdate, AgentExecutionCreate
from app.core.timeutils import safe_duration_ms


# ─── Errors ──────────────────────────────────────────


class AgentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AgentNotFoundError(AgentError):
    def __init__(self):
        super().__init__("Agent not found", status_code=404)


class InvalidTransitionError(AgentError):
    def __init__(self, current: ExecutionStatus, target: ExecutionStatus):
        super().__init__(
            f"Cannot transition from {current.value} to {target.value}",
            status_code=400,
        )


# ─── State Machine ──────────────────────────────────

# Valid execution status transitions
EXECUTION_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.PENDING: {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED},
    ExecutionStatus.RUNNING: {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.PAUSED, ExecutionStatus.CANCELLED},
    ExecutionStatus.PAUSED: {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED},
    ExecutionStatus.COMPLETED: set(),
    ExecutionStatus.FAILED: set(),
    ExecutionStatus.CANCELLED: set(),
}


def validate_transition(current: ExecutionStatus, target: ExecutionStatus) -> None:
    """Validate an execution status transition."""
    if target not in EXECUTION_TRANSITIONS.get(current, set()):
        raise InvalidTransitionError(current, target)


# ─── Agent CRUD ─────────────────────────────────────


async def create_agent(db: AsyncSession, workspace_id: UUID, agent_in: AgentCreate) -> Agent:
    """Create a new agent within a workspace."""
    agent = Agent(
        workspace_id=workspace_id,
        name=agent_in.name,
        description=agent_in.description,
        system_prompt=agent_in.system_prompt,
        model_provider=agent_in.model_provider,
        model_name=agent_in.model_name,
        temperature=agent_in.temperature,
        max_tokens=agent_in.max_tokens,
        config=agent_in.config,
        tool_ids=agent_in.tool_ids,
        status=AgentStatus.DRAFT,
    )
    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return agent


async def get_agent_by_id(db: AsyncSession, agent_id: UUID) -> Agent | None:
    """Get an agent by ID."""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def list_workspace_agents(
    db: AsyncSession, workspace_id: UUID, page: int = 1, page_size: int = 50
) -> tuple[list[Agent], int]:
    """List all agents in a workspace with pagination."""
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(Agent.id)).where(
            Agent.workspace_id == workspace_id,
            Agent.deleted_at.is_(None),
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Agent)
        .where(
            Agent.workspace_id == workspace_id,
            Agent.deleted_at.is_(None),
        )
        .order_by(Agent.updated_at.desc().nulls_last(), Agent.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    agents = result.scalars().all()
    return list(agents), total


async def update_agent(db: AsyncSession, agent: Agent, agent_in: AgentUpdate) -> Agent:
    """Update an agent."""
    update_data = agent_in.model_dump(exclude_unset=True)

    # Increment version on configuration changes
    config_fields = {"system_prompt", "model_provider", "model_name", "temperature", "max_tokens", "config", "tool_ids"}
    if config_fields & set(update_data.keys()):
        agent.version += 1

    for field, value in update_data.items():
        setattr(agent, field, value)

    await db.flush()
    await db.refresh(agent)
    return agent


async def delete_agent(db: AsyncSession, agent: Agent) -> None:
    """Soft-delete an agent."""
    agent.deleted_at = datetime.now(timezone.utc)
    agent.status = AgentStatus.ARCHIVED
    await db.flush()


# ─── Execution Lifecycle ────────────────────────────


async def create_execution(
    db: AsyncSession, agent_id: UUID, exec_in: AgentExecutionCreate | None = None
) -> AgentExecution:
    """Create a new execution for an agent."""
    agent = await get_agent_by_id(db, agent_id)
    if agent is None:
        raise AgentNotFoundError()

    # Generate session_id if not provided
    session_id = exec_in.session_id if exec_in and exec_in.session_id else str(uuid.uuid4())

    execution = AgentExecution(
        agent_id=agent_id,
        session_id=session_id,
        status=ExecutionStatus.PENDING,
        input_data=exec_in.input_data if exec_in else None,
    )
    db.add(execution)
    await db.flush()
    await db.refresh(execution)
    return execution


async def get_execution_by_id(db: AsyncSession, execution_id: UUID) -> AgentExecution | None:
    """Get an execution by ID."""
    result = await db.execute(
        select(AgentExecution).where(AgentExecution.id == execution_id)
    )
    return result.scalar_one_or_none()


async def list_agent_executions(
    db: AsyncSession,
    agent_id: UUID,
    page: int = 1,
    page_size: int = 50,
    status_filter: ExecutionStatus | None = None,
) -> tuple[list[AgentExecution], int]:
    """List executions for an agent."""
    offset = (page - 1) * page_size

    conditions = [AgentExecution.agent_id == agent_id]
    if status_filter:
        conditions.append(AgentExecution.status == status_filter)

    count_result = await db.execute(select(func.count(AgentExecution.id)).where(*conditions))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(AgentExecution)
        .where(*conditions)
        .order_by(AgentExecution.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    executions = result.scalars().all()
    return list(executions), total


async def start_execution(db: AsyncSession, execution: AgentExecution) -> AgentExecution:
    """Start an execution (PENDING -> RUNNING)."""
    validate_transition(execution.status, ExecutionStatus.RUNNING)
    execution.status = ExecutionStatus.RUNNING
    execution.started_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(execution)
    return execution


async def complete_execution(
    db: AsyncSession,
    execution: AgentExecution,
    output_data: dict | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    cost_usd: float | None = None,
) -> AgentExecution:
    """Complete an execution (RUNNING -> COMPLETED)."""
    validate_transition(execution.status, ExecutionStatus.COMPLETED)

    now = datetime.now(timezone.utc)
    execution.status = ExecutionStatus.COMPLETED
    execution.completed_at = now
    execution.output_data = output_data
    execution.prompt_tokens = prompt_tokens
    execution.completion_tokens = completion_tokens
    if prompt_tokens is not None and completion_tokens is not None:
        execution.total_tokens = prompt_tokens + completion_tokens
    execution.cost_usd = cost_usd

    if execution.started_at:
        execution.duration_ms = safe_duration_ms(execution.started_at)

    await db.flush()
    await db.refresh(execution)
    return execution


async def fail_execution(
    db: AsyncSession,
    execution: AgentExecution,
    error_message: str,
) -> AgentExecution:
    """Fail an execution (RUNNING -> FAILED)."""
    validate_transition(execution.status, ExecutionStatus.FAILED)

    now = datetime.now(timezone.utc)
    execution.status = ExecutionStatus.FAILED
    execution.completed_at = now
    execution.error_message = error_message

    if execution.started_at:
        execution.duration_ms = safe_duration_ms(execution.started_at)

    await db.flush()
    await db.refresh(execution)
    return execution


async def cancel_execution(db: AsyncSession, execution: AgentExecution) -> AgentExecution:
    """Cancel an execution (any active state -> CANCELLED)."""
    validate_transition(execution.status, ExecutionStatus.CANCELLED)

    now = datetime.now(timezone.utc)
    execution.status = ExecutionStatus.CANCELLED
    execution.completed_at = now

    if execution.started_at:
        execution.duration_ms = safe_duration_ms(execution.started_at)

    await db.flush()
    await db.refresh(execution)
    return execution


async def pause_execution(db: AsyncSession, execution: AgentExecution) -> AgentExecution:
    """Pause an execution (RUNNING -> PAUSED)."""
    validate_transition(execution.status, ExecutionStatus.PAUSED)
    execution.status = ExecutionStatus.PAUSED
    await db.flush()
    await db.refresh(execution)
    return execution


async def resume_execution(db: AsyncSession, execution: AgentExecution) -> AgentExecution:
    """Resume a paused execution (PAUSED -> RUNNING)."""
    validate_transition(execution.status, ExecutionStatus.RUNNING)
    execution.status = ExecutionStatus.RUNNING
    await db.flush()
    await db.refresh(execution)
    return execution


# ─── Session Management ─────────────────────────────


async def list_session_executions(
    db: AsyncSession, session_id: str, workspace_id: UUID | None = None, agent_id: UUID | None = None
) -> list[AgentExecution]:
    """List all executions in a session, optionally scoped to a workspace."""
    query = select(AgentExecution)

    if workspace_id:
        # Join through agent to filter by workspace
        query = query.join(Agent, AgentExecution.agent_id == Agent.id).where(
            Agent.workspace_id == workspace_id
        )

    conditions = [AgentExecution.session_id == session_id]
    if agent_id:
        conditions.append(AgentExecution.agent_id == agent_id)

    query = query.where(*conditions).order_by(AgentExecution.created_at.asc())
    result = await db.execute(query)
    return list(result.scalars().all())
