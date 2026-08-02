"""Prompt models."""

import uuid
from sqlalchemy import String, Text, ForeignKey, Enum as SAEnum, JSON, Integer, Boolean, UniqueConstraint
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import BaseModel


class PromptType(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TEMPLATE = "template"


class Prompt(BaseModel):
    __tablename__ = "prompts"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_type: Mapped[PromptType] = mapped_column(
        SAEnum(PromptType, name="prompt_type"),
        default=PromptType.TEMPLATE,
        nullable=False,
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_version: Mapped[int] = mapped_column(default=1, nullable=False)

    versions = relationship("PromptVersion", back_populates="prompt", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Prompt {self.slug} v{self.current_version}>"


class PromptVersion(BaseModel):
    __tablename__ = "prompt_versions"

    prompt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    template_variables: Mapped[list | None] = mapped_column(JSON, nullable=True)
    commit_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    prompt = relationship("Prompt", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),
    )

    def __repr__(self):
        return f"<PromptVersion {self.prompt_id} v{self.version}>"
