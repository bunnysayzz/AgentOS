"""Execution graph schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.execution_graph import NodeType, NodeStatus


class ExecutionGraphNodeResponse(BaseModel):
    id: UUID
    execution_id: UUID
    parent_node_id: UUID | None
    node_type: NodeType
    node_name: str | None
    status: NodeStatus
    input_data: dict | None
    output_data: dict | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    model_provider: str | None
    model_name: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionGraphResponse(BaseModel):
    """Full execution graph with nodes."""
    nodes: list[ExecutionGraphNodeResponse]
    total_duration_ms: int = 0
    total_cost_usd: float = 0
    total_tokens: int = 0
