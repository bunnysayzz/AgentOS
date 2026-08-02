"""Artifact store model for versioned assets."""

import uuid
from sqlalchemy import String, Text, ForeignKey, BigInteger, JSON, Integer
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Artifact(BaseModel):
    __tablename__ = "artifacts"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    artifact_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    def __repr__(self):
        return f"<Artifact {self.name} ({self.content_type})>"
