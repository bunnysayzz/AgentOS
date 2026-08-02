"""Memory model."""

import uuid
from sqlalchemy import String, Text, ForeignKey, JSON, Float
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class MemoryEntry(BaseModel):
    __tablename__ = "memory_entries"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)

    # Memory content
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # For vector search
    embedding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    entry_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Memory type
    memory_type: Mapped[str] = mapped_column(
        String(32), default="conversation", nullable=False
    )  # conversation, episodic, semantic, procedural

    # Relevance/importance score (for memory consolidation)
    importance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    access_count: Mapped[int] = mapped_column(default=0, nullable=False)

    def __repr__(self):
        return f"<MemoryEntry {self.id} ({self.memory_type})>"
