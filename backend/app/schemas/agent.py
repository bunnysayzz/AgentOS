"""Agent schemas."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.agent import AgentStatus, ExecutionStatus


# ─── Agent ────────────────────────────────────────────────

class AgentBase(BaseModel):
    name: str = Field(..., max_length=256)
    description: str | None = Field(None, max_length=4096)
    system_prompt: str | None = None
    model_provider: str = Field("openai", max_length=64)
    model_name: str = Field("gpt-4o", max_length=128)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1, le=128000)
    config: dict | None = None
    tool_ids: list[str] | None = None


class AgentCreate(AgentBase):
    pass


class AgentFromTemplateCreate(BaseModel):
    """Create an agent from a curated template."""

    template_id: str = Field(..., min_length=1, max_length=64)


class AgentTemplate(BaseModel):
    """A curated, ready-to-use agent template."""

    id: str
    name: str
    description: str | None = None
    system_prompt: str | None = None
    model_provider: str = "openai"
    model_name: str = "gpt-4o"


class AgentUpdate(BaseModel):
    name: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=4096)
    system_prompt: str | None = None
    model_provider: str | None = Field(None, max_length=64)
    model_name: str | None = Field(None, max_length=128)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=128000)
    config: dict | None = None
    tool_ids: list[str] | None = None
    status: AgentStatus | None = None


class AgentResponse(AgentBase):
    id: UUID
    workspace_id: UUID
    status: AgentStatus
    version: int
    created_at: datetime
    updated_at: datetime | None
    # Gallery visibility (agent published to the public community gallery).
    published: bool = False
    published_at: datetime | None = None

    model_config = {"from_attributes": True}


# ─── Agent Execution ──────────────────────────────────────

class AgentExecutionBase(BaseModel):
    input_data: dict | None = None
    session_id: str | None = Field(None, max_length=128)


class AgentExecutionCreate(AgentExecutionBase):
    """Create an agent execution. agent_id is optional — it's set from the URL path."""
    agent_id: UUID | None = None


class AgentExecutionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    session_id: str | None
    status: ExecutionStatus
    input_data: dict | None
    output_data: dict | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_usd: float | None
    created_at: datetime

    model_config = {"from_attributes": True}
