"""Execution Graph service — node-level execution tracing and inspection."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution_graph import (
    ExecutionGraphNode,
    NodeType,
    NodeStatus,
)


# ─── Errors ──────────────────────────────────────────


class ExecutionGraphError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NodeNotFoundError(ExecutionGraphError):
    def __init__(self):
        super().__init__("Execution graph node not found", status_code=404)


# ─── CRUD ────────────────────────────────────────────


async def create_node(
    db: AsyncSession,
    execution_id: UUID,
    node_type: NodeType,
    node_name: str | None = None,
    parent_node_id: UUID | None = None,
    input_data: dict | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
) -> ExecutionGraphNode:
    """Create a new node in the execution graph."""
    node = ExecutionGraphNode(
        execution_id=execution_id,
        parent_node_id=parent_node_id,
        node_type=node_type,
        node_name=node_name,
        status=NodeStatus.PENDING,
        input_data=input_data,
        model_provider=model_provider,
        model_name=model_name,
    )
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return node


async def get_node_by_id(db: AsyncSession, node_id: UUID) -> ExecutionGraphNode | None:
    result = await db.execute(
        select(ExecutionGraphNode).where(ExecutionGraphNode.id == node_id)
    )
    return result.scalar_one_or_none()


async def update_node_status(
    db: AsyncSession,
    node: ExecutionGraphNode,
    status: NodeStatus,
    output_data: dict | None = None,
    error_message: str | None = None,
    duration_ms: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    cost_usd: float | None = None,
    checkpoint_path: str | None = None,
) -> ExecutionGraphNode:
    """Update node status and execution metrics."""
    node.status = status

    if output_data is not None:
        node.output_data = output_data
    if error_message is not None:
        node.error_message = error_message
    if duration_ms is not None:
        node.duration_ms = duration_ms
    if prompt_tokens is not None:
        node.prompt_tokens = prompt_tokens
    if completion_tokens is not None:
        node.completion_tokens = completion_tokens
    if cost_usd is not None:
        node.cost_usd = cost_usd
    if checkpoint_path is not None:
        node.checkpoint_path = checkpoint_path

    # Timing
    if status == NodeStatus.RUNNING and node.started_at is None:
        node.started_at = datetime.now(timezone.utc)
    elif status in (NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.CANCELLED):
        node.completed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(node)
    return node


async def list_execution_nodes(
    db: AsyncSession, execution_id: UUID
) -> list[ExecutionGraphNode]:
    """Get all nodes for an execution, ordered by creation."""
    result = await db.execute(
        select(ExecutionGraphNode)
        .where(ExecutionGraphNode.execution_id == execution_id)
        .order_by(ExecutionGraphNode.created_at.asc())
    )
    return list(result.scalars().all())


async def get_execution_graph(
    db: AsyncSession, execution_id: UUID
) -> tuple[list[ExecutionGraphNode], dict]:
    """Get full execution graph with summary stats."""
    nodes = await list_execution_nodes(db, execution_id)

    total_duration = sum(n.duration_ms or 0 for n in nodes if n.duration_ms)
    total_cost = sum(n.cost_usd or 0 for n in nodes if n.cost_usd)
    total_tokens = sum((n.prompt_tokens or 0) + (n.completion_tokens or 0) for n in nodes)

    stats = {
        "total_duration_ms": total_duration,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "node_count": len(nodes),
        "by_status": {},
        "by_type": {},
    }

    for n in nodes:
        stats["by_status"][n.status.value] = stats["by_status"].get(n.status.value, 0) + 1
        stats["by_type"][n.node_type.value] = stats["by_type"].get(n.node_type.value, 0) + 1

    return nodes, stats


async def get_node_children(
    db: AsyncSession, parent_node_id: UUID
) -> list[ExecutionGraphNode]:
    """Get child nodes of a given node."""
    result = await db.execute(
        select(ExecutionGraphNode)
        .where(ExecutionGraphNode.parent_node_id == parent_node_id)
        .order_by(ExecutionGraphNode.created_at.asc())
    )
    return list(result.scalars().all())
