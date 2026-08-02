"""Secret model."""

import uuid
from sqlalchemy import String, Text, ForeignKey, Enum as SAEnum, Boolean
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import BaseModel


class SecretProvider(str, enum.Enum):
    BUILTIN = "builtin"
    VAULT = "vault"
    AWS_SECRETS = "aws_secrets"
    GCP_SECRETS = "gcp_secrets"


class Secret(BaseModel):
    __tablename__ = "secrets"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    provider: Mapped[SecretProvider] = mapped_column(
        SAEnum(SecretProvider, name="secret_provider"),
        default=SecretProvider.BUILTIN,
        nullable=False,
    )
    environment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Secret {self.slug} ({self.provider.value})>"
