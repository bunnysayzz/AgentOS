"""Execution graph model."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Enum as SAEnum, JSON, DateTime
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import BaseModel


class NodeType(str, enum.Enum):
    AGENT_CALL = "agent_call"
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    CONDITION = "condition"
    LOOP = "loop"
    HUMAN_INPUT = "human_input"
    APPROVAL_GATE = "approval_gate"
    SUB_WORKFLOW = "sub_workflow"
    FUNCTION = "function"


class NodeStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    AWAITING_INPUT = "awaiting_input"


class ExecutionGraphNode(BaseModel):
    __tablename__ = "execution_graph_nodes"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("agent_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_node_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("execution_graph_nodes.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Node metadata
    node_type: Mapped[NodeType] = mapped_column(
        SAEnum(NodeType, name="node_type"),
        nullable=False,
    )
    node_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[NodeStatus] = mapped_column(
        SAEnum(NodeStatus, name="node_status"),
        default=NodeStatus.PENDING,
        nullable=False,
    )

    # Execution data
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    # LLM-specific tracking
    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(nullable=True)

    # Checkpointing
    checkpoint_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Relationships
    execution = relationship("AgentExecution", back_populates="graph_nodes")
    # Note: parent/children self-referential relationships removed because
    # the service layer handles parent-child traversal via direct queries.
    # Self-referential remote_side causes mapper issues with inherited id columns.

    def __repr__(self):
        return f"<ExecutionGraphNode {self.node_name} ({self.node_type.value}:{self.status.value})>"
