"""Workflow Engine service - DAG validation, execution lifecycle, scheduling."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow, WorkflowExecution, WorkflowStatus, WorkflowExecutionStatus
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.core.timeutils import safe_duration_ms


# ─── Errors ──────────────────────────────────────────


class WorkflowError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class WorkflowNotFoundError(WorkflowError):
    def __init__(self):
        super().__init__("Workflow not found", status_code=404)


class InvalidDAGError(WorkflowError):
    pass


# ─── DAG Validation ────────────────────────────────


def validate_dag(dag: dict | None) -> list[str]:
    """Validate a DAG definition. Returns list of validation errors (empty = valid)."""
    errors = []
    if not dag:
        return ["DAG definition is required"]

    nodes = dag.get("nodes", [])
    edges = dag.get("edges", [])

    if not nodes:
        errors.append("DAG must have at least one node")
        return errors

    # Validate nodes
    node_ids = set()
    for i, node in enumerate(nodes):
        nid = node.get("id")
        if not nid:
            errors.append(f"Node {i} is missing an 'id' field")
        elif nid in node_ids:
            errors.append(f"Duplicate node id: {nid}")
        else:
            node_ids.add(nid)

        if not node.get("type"):
            errors.append(f"Node {nid or i} is missing a 'type' field")

    # Validate edges
    for i, edge in enumerate(edges):
        source = edge.get("source")
        target = edge.get("target")
        if source and source not in node_ids:
            errors.append(f"Edge {i}: source '{source}' not found in nodes")
        if target and target not in node_ids:
            errors.append(f"Edge {i}: target '{target}' not found in nodes")

    # Check for cycles (simple DFS)
    if node_ids and _has_cycle(nodes, edges):
        errors.append("DAG contains a cycle — workflows must be acyclic")

    # Check for disconnected nodes
    if edges:
        connected = set()
        for edge in edges:
            if edge.get("source"):
                connected.add(edge["source"])
            if edge.get("target"):
                connected.add(edge["target"])
        disconnected = node_ids - connected
        if len(disconnected) == len(node_ids):
            pass  # Single node with no edges is valid
        elif disconnected:
            for nid in disconnected:
                errors.append(f"Node '{nid}' is disconnected (no incoming or outgoing edges)")

    return errors


def _has_cycle(nodes: list[dict], edges: list[dict]) -> bool:
    """Detect cycles in a directed graph using DFS."""
    adj = {n["id"]: [] for n in nodes}
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src and tgt:
            adj[src].append(tgt)

    visited = set()
    rec_stack = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.discard(node)
        return False

    for node in adj:
        if node not in visited:
            if dfs(node):
                return True
    return False


# ─── Workflow CRUD ────────────────────────────────


async def create_workflow(db: AsyncSession, workspace_id: UUID, wf_in: WorkflowCreate) -> Workflow:
    """Create a new workflow with DAG validation."""
    if wf_in.dag_definition:
        errors = validate_dag(wf_in.dag_definition)
        if errors:
            raise InvalidDAGError("; ".join(errors))

    workflow = Workflow(
        workspace_id=workspace_id,
        name=wf_in.name,
        description=wf_in.description,
        dag_definition=wf_in.dag_definition,
        trigger_type=wf_in.trigger_type,
        trigger_config=wf_in.trigger_config,
        schedule_cron=wf_in.schedule_cron,
        timeout_seconds=wf_in.timeout_seconds,
        status=WorkflowStatus.DRAFT,
    )
    db.add(workflow)
    await db.flush()
    await db.refresh(workflow)
    return workflow


async def get_workflow_by_id(db: AsyncSession, workflow_id: UUID) -> Workflow | None:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def list_workspace_workflows(
    db: AsyncSession, workspace_id: UUID, page: int = 1, page_size: int = 50
) -> tuple[list[Workflow], int]:
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(Workflow.id)).where(
            Workflow.workspace_id == workspace_id,
            Workflow.deleted_at.is_(None),
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Workflow)
        .where(Workflow.workspace_id == workspace_id, Workflow.deleted_at.is_(None))
        .order_by(Workflow.updated_at.desc().nulls_last(), Workflow.created_at.desc())
        .offset(offset).limit(page_size)
    )
    return list(result.scalars().all()), total


async def update_workflow(db: AsyncSession, workflow: Workflow, wf_in: WorkflowUpdate) -> Workflow:
    update_data = wf_in.model_dump(exclude_unset=True)

    # Re-validate DAG if changed
    if "dag_definition" in update_data and update_data["dag_definition"]:
        errors = validate_dag(update_data["dag_definition"])
        if errors:
            raise InvalidDAGError("; ".join(errors))
        workflow.version += 1

    for field, value in update_data.items():
        setattr(workflow, field, value)

    await db.flush()
    await db.refresh(workflow)
    return workflow


async def delete_workflow(db: AsyncSession, workflow: Workflow) -> None:
    workflow.deleted_at = datetime.now(timezone.utc)
    workflow.status = WorkflowStatus.ARCHIVED
    await db.flush()


# ─── Execution Lifecycle ──────────────────────────


async def create_execution(
    db: AsyncSession, workflow: Workflow, input_data: dict | None = None,
    triggered_by: str | None = None,
) -> WorkflowExecution:
    if workflow.status != WorkflowStatus.ACTIVE:
        raise WorkflowError(f"Cannot execute workflow in '{workflow.status.value}' status")

    execution = WorkflowExecution(
        workflow_id=workflow.id,
        status=WorkflowExecutionStatus.PENDING,
        input_data=input_data,
        triggered_by=triggered_by or "user",
    )
    db.add(execution)
    await db.flush()
    await db.refresh(execution)
    return execution


async def get_execution(db: AsyncSession, execution_id: UUID) -> WorkflowExecution | None:
    result = await db.execute(select(WorkflowExecution).where(WorkflowExecution.id == execution_id))
    return result.scalar_one_or_none()


async def list_executions(
    db: AsyncSession, workflow_id: UUID, page: int = 1, page_size: int = 50
) -> tuple[list[WorkflowExecution], int]:
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(WorkflowExecution.id)).where(WorkflowExecution.workflow_id == workflow_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .order_by(WorkflowExecution.created_at.desc())
        .offset(offset).limit(page_size)
    )
    return list(result.scalars().all()), total


async def start_execution(db: AsyncSession, execution: WorkflowExecution) -> WorkflowExecution:
    if execution.status != WorkflowExecutionStatus.PENDING:
        raise WorkflowError(f"Cannot start execution in '{execution.status.value}' status")
    execution.status = WorkflowExecutionStatus.RUNNING
    execution.started_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(execution)
    return execution


async def complete_execution(
    db: AsyncSession, execution: WorkflowExecution, output_data: dict | None = None
) -> WorkflowExecution:
    if execution.status != WorkflowExecutionStatus.RUNNING:
        raise WorkflowError(f"Cannot complete execution in '{execution.status.value}' status")
    now = datetime.now(timezone.utc)
    execution.status = WorkflowExecutionStatus.COMPLETED
    execution.completed_at = now
    execution.output_data = output_data
    if execution.started_at:
        execution.duration_ms = safe_duration_ms(execution.started_at)
    await db.flush()
    await db.refresh(execution)
    return execution


async def fail_execution(db: AsyncSession, execution: WorkflowExecution, error: str) -> WorkflowExecution:
    if execution.status not in (WorkflowExecutionStatus.RUNNING, WorkflowExecutionStatus.PENDING):
        raise WorkflowError(f"Cannot fail execution in '{execution.status.value}' status")
    now = datetime.now(timezone.utc)
    execution.status = WorkflowExecutionStatus.FAILED
    execution.completed_at = now
    execution.error_message = error
    if execution.started_at:
        execution.duration_ms = safe_duration_ms(execution.started_at)
    await db.flush()
    await db.refresh(execution)
    return execution


async def pause_execution(db: AsyncSession, execution: WorkflowExecution) -> WorkflowExecution:
    if execution.status != WorkflowExecutionStatus.RUNNING:
        raise WorkflowError(f"Cannot pause execution in '{execution.status.value}' status")
    execution.status = WorkflowExecutionStatus.PAUSED
    await db.flush()
    await db.refresh(execution)
    return execution


async def resume_execution(db: AsyncSession, execution: WorkflowExecution) -> WorkflowExecution:
    if execution.status != WorkflowExecutionStatus.PAUSED:
        raise WorkflowError(f"Cannot resume execution in '{execution.status.value}' status")
    execution.status = WorkflowExecutionStatus.RUNNING
    await db.flush()
    await db.refresh(execution)
    return execution


async def cancel_execution(db: AsyncSession, execution: WorkflowExecution) -> WorkflowExecution:
    if execution.status not in (WorkflowExecutionStatus.PENDING, WorkflowExecutionStatus.RUNNING, WorkflowExecutionStatus.AWAITING_APPROVAL):
        raise WorkflowError(f"Cannot cancel execution in '{execution.status.value}' status")
    now = datetime.now(timezone.utc)
    execution.status = WorkflowExecutionStatus.CANCELLED
    execution.completed_at = now
    if execution.started_at:
        execution.duration_ms = safe_duration_ms(execution.started_at)
    await db.flush()
    await db.refresh(execution)
    return execution


async def request_approval(db: AsyncSession, execution: WorkflowExecution) -> WorkflowExecution:
    execution.status = WorkflowExecutionStatus.AWAITING_APPROVAL
    await db.flush()
    await db.refresh(execution)
    return execution


async def approve_execution(db: AsyncSession, execution: WorkflowExecution) -> WorkflowExecution:
    if execution.status != WorkflowExecutionStatus.AWAITING_APPROVAL:
        raise WorkflowError(f"Cannot approve execution in '{execution.status.value}' status")
    # Re-check parent workflow is still active
    wf = await get_workflow_by_id(db, execution.workflow_id)
    if wf and wf.status != WorkflowStatus.ACTIVE:
        raise WorkflowError(f"Cannot approve — workflow is '{wf.status.value}', must be 'active'")
    execution.status = WorkflowExecutionStatus.RUNNING
    await db.flush()
    await db.refresh(execution)
    return execution
