"""Base model mixin with common columns."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Boolean, func
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, declared_attr

from app.core.database import Base


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime | None]:
        return mapped_column(
            DateTime(timezone=True),
            onupdate=func.now(),
            nullable=True,
        )

    @declared_attr
    def deleted_at(cls) -> Mapped[datetime | None]:
        """Soft delete timestamp."""
        return mapped_column(DateTime(timezone=True), nullable=True, default=None)


class UUIDMixin:
    """Mixin that adds a UUID primary key."""

    @declared_attr
    def id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            Uuid(),
            primary_key=True,
            default=uuid.uuid4,
            index=True,
        )


class BaseModel(Base, TimestampMixin, UUIDMixin):
    """Abstract base model with UUID pk and timestamps."""

    __abstract__ = True
