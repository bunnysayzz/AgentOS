"""MCP Gateway schemas - chat, completion, models, cost tracking."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.mcp import LLMProvider


# ─── Chat/Completion ────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(system|user|assistant|tool)$")
    content: str
    name: str | None = Field(None, max_length=64)
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="gpt-4o", max_length=128)
    messages: list[ChatMessage]
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=128000)
    stream: bool = False
    tools: list[dict] | None = None
    tool_choice: str | None = None  # "auto", "required", "none", or specific tool


class ChatCompletionResponse(BaseModel):
    id: str
    model: str
    provider: LLMProvider
    choices: list[dict]
    usage: dict  # {prompt_tokens, completion_tokens, total_tokens}
    cost_usd: float
    created: datetime


# ─── Models ─────────────────────────────────────────

class ModelInfo(BaseModel):
    id: str  # e.g. "openai/gpt-4o"
    provider: LLMProvider
    model_name: str
    capabilities: list[str]
    input_price_per_1k: float
    output_price_per_1k: float
    context_window: int
    max_output_tokens: int
    is_active: bool
    description: str | None


class ModelListResponse(BaseModel):
    models: list[ModelInfo]
    total: int


# ─── Cost Dashboard ─────────────────────────────────

class CostSummary(BaseModel):
    total_cost_usd: float = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_calls: int = 0
    avg_cost_per_call: float = 0
    period_days: int = 30


class CostByProvider(BaseModel):
    provider: LLMProvider
    cost_usd: float
    calls: int
    tokens: int


class CostByModel(BaseModel):
    model: str
    provider: LLMProvider
    cost_usd: float
    calls: int
    tokens: int


class CostDashboardResponse(BaseModel):
    summary: CostSummary
    by_provider: list[CostByProvider]
    by_model: list[CostByModel]


# ─── Provider Config ────────────────────────────────

class ProviderConfigCreate(BaseModel):
    provider: LLMProvider
    api_key: str = Field(..., min_length=1)
    base_url: str | None = None
    default_model: str | None = None
    config: dict | None = None


class ProviderConfigResponse(BaseModel):
    provider: LLMProvider
    default_model: str | None
    is_configured: bool
    base_url: str | None
    created_at: datetime


# ─── MCP Server Marketplace ─────────────────────────

class MCPMarketplaceItem(BaseModel):
    """A curated MCP server listing for one-click discovery."""

    id: str
    name: str
    description: str
    command: str
    args: list[str]
    env_vars: list[str]
    homepage: str
    category: str
