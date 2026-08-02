"""Tool models."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Enum as SAEnum, JSON, Boolean, DateTime
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import BaseModel


class ToolType(str, enum.Enum):
    BUILTIN = "builtin"
    CUSTOM = "custom"
    MCP = "mcp"
    WEBHOOK = "webhook"


class ToolAuthType(str, enum.Enum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BEARER = "bearer"


class Tool(BaseModel):
    __tablename__ = "tools"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tool definition
    tool_type: Mapped[ToolType] = mapped_column(
        SAEnum(ToolType, name="tool_type"),
        default=ToolType.CUSTOM,
        nullable=False,
    )
    source: Mapped[str | None] = mapped_column(String(512), nullable=True)
    schema_definition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Auth
    auth_type: Mapped[ToolAuthType] = mapped_column(
        SAEnum(ToolAuthType, name="tool_auth_type"),
        default=ToolAuthType.NONE,
        nullable=False,
    )
    auth_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)

    # Tags
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    def __repr__(self):
        return f"<Tool {self.slug} ({self.tool_type.value})>"


class ToolExecution(BaseModel):
    __tablename__ = "tool_executions"

    tool_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("agent_executions.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    input_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<ToolExecution {self.id} ({self.status})>"
