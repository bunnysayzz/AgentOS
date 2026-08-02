"""MCP Gateway models - LLM provider configs, model registry, cost tracking."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Enum as SAEnum, JSON, Boolean, Float, DateTime
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import BaseModel


class LLMProvider(str, enum.Enum):
    # Major providers
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    AWS_BEDROCK = "aws_bedrock"
    OLLAMA = "ollama"
    CUSTOM = "custom"

    # Free / community providers (from kilo config)
    BLUESMINDS = "bluesminds"
    GROQ = "groq"
    CEREBRAS = "cerebras"
    OPENROUTER = "openrouter"
    MISTRAL = "mistral"
    HUGGINGFACE = "huggingface"
    NVIDIA_NIM = "nvidia_nim"
    GITHUB_MODELS = "github_models"
    CLOUDFLARE = "cloudflare"
    SHUTTLEAI = "shuttleai"
    AIHUBMIX = "aihubmix"
    KLUSTER_AI = "kluster_ai"
    ZHIPU_ZAI = "zhipu_zai"
    TOGETHER_AI = "together_ai"
    SAMBANOVA = "sambanova"
    HYPERBOLIC = "hyperbolic"
    FIREWORKS = "fireworks"
    DEEPINFRA = "deepinfra"
    NOVITA = "novita"
    AIML_API = "aiml_api"
    SWIFTROUTER = "swiftrouter"
    DEEPSEEK = "deepseek"
    API_FREE_LLM = "apifreellm"
    LLMAPI = "llmapi"
    POLLINATIONS = "pollinations"
    NAGA_AI = "naga_ai"


class ProviderConfig(BaseModel):
    """Stores encrypted API keys and config for LLM providers."""
    __tablename__ = "provider_configs"

    provider: Mapped[LLMProvider] = mapped_column(
        SAEnum(LLMProvider, name="pc_provider"),
        primary_key=True,
        nullable=False,
    )
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    default_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Override id from BaseModel — ProviderConfig uses provider as PK
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )

    def __repr__(self):
        return f"<ProviderConfig {self.provider.value}>"


class ModelCapability(str, enum.Enum):
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"


class LLMCall(BaseModel):
    """Records every LLM API call for cost tracking and observability."""
    __tablename__ = "llm_calls"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("agent_executions.id", ondelete="SET NULL"), nullable=True
    )

    # Provider & model
    provider: Mapped[LLMProvider] = mapped_column(
        SAEnum(LLMProvider, name="llm_provider"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Request
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    messages: Mapped[list | None] = mapped_column(JSON, nullable=True)  # Array of message dicts
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(nullable=True)

    # Response
    response_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Token usage
    prompt_tokens: Mapped[int] = mapped_column(default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(default=0, nullable=False)

    # Cost (calculated from token counts + model pricing)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Performance
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    is_cached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Error tracking
    is_error: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Streaming
    is_streaming: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<LLMCall {self.provider.value}/{self.model_name} ({self.total_tokens} tokens, ${self.cost_usd:.4f})>"


class ModelRegistry(BaseModel):
    """Registry of available models and their pricing."""
    __tablename__ = "model_registry"

    provider: Mapped[LLMProvider] = mapped_column(
        SAEnum(LLMProvider, name="model_registry_provider"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Capabilities
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Pricing (per 1K tokens)
    input_price_per_1k: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    output_price_per_1k: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Context window
    context_window: Mapped[int] = mapped_column(default=4096, nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(default=4096, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    registry_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    def __repr__(self):
        return f"<Model {self.provider.value}/{self.model_name}>"
