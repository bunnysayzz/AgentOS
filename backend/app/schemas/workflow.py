"""Workflow schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.workflow import WorkflowStatus, WorkflowExecutionStatus


class WorkflowBase(BaseModel):
    name: str = Field(..., max_length=256)
    description: str | None = Field(None, max_length=4096)
    dag_definition: dict | None = None
    trigger_type: str | None = Field(None, max_length=64)
    trigger_config: dict | None = None
    schedule_cron: str | None = Field(None, max_length=128)
    timeout_seconds: int | None = None


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=4096)
    dag_definition: dict | None = None
    trigger_type: str | None = Field(None, max_length=64)
    trigger_config: dict | None = None
    status: WorkflowStatus | None = None
    schedule_cron: str | None = Field(None, max_length=128)
    timeout_seconds: int | None = None


class WorkflowResponse(WorkflowBase):
    id: UUID
    workspace_id: UUID
    status: WorkflowStatus
    version: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class WorkflowExecutionResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    status: WorkflowExecutionStatus
    triggered_by: str | None
    trigger_event: dict | None
    input_data: dict | None
    output_data: dict | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
