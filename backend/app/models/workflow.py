"""Workflow models."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Enum as SAEnum, JSON, DateTime, Integer
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import BaseModel


class WorkflowStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class WorkflowExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"


class Workflow(BaseModel):
    __tablename__ = "workflows"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # DAG definition (dict with nodes and edges)
    dag_definition: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Trigger config
    trigger_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[WorkflowStatus] = mapped_column(
        SAEnum(WorkflowStatus, name="workflow_status"),
        default=WorkflowStatus.DRAFT,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)

    # Scheduling
    schedule_cron: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="workflows")
    executions = relationship("WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Workflow {self.name} ({self.status.value})>"


class WorkflowExecution(BaseModel):
    __tablename__ = "workflow_executions"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[WorkflowExecutionStatus] = mapped_column(
        SAEnum(WorkflowExecutionStatus, name="workflow_execution_status"),
        default=WorkflowExecutionStatus.PENDING,
        nullable=False,
    )

    # Trigger info
    triggered_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger_event: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Input/output
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    # Checkpoint
    checkpoint_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    workflow = relationship("Workflow", back_populates="executions")

    def __repr__(self):
        return f"<WorkflowExecution {self.id} ({self.status.value})>"
