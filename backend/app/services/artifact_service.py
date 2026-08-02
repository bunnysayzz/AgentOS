"""Artifact Store service — versioned asset tracking with storage path management."""

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import Artifact
from app.schemas.artifact import ArtifactCreate, ArtifactUpdate


# ─── Errors ──────────────────────────────────────────


class ArtifactError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ArtifactNotFoundError(ArtifactError):
    def __init__(self):
        super().__init__("Artifact not found", status_code=404)


# ─── Helpers ─────────────────────────────────────────


def _compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_storage_path(workspace_id: UUID, name: str, version: int) -> str:
    """Build a deterministic storage path for an artifact."""
    sanitized = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    return f"workspaces/{workspace_id}/artifacts/{sanitized}/v{version}"


# ─── CRUD ────────────────────────────────────────────


async def create_artifact(
    db: AsyncSession,
    workspace_id: UUID,
    artifact_in: ArtifactCreate,
    data: bytes | None = None,
) -> Artifact:
    """Register a new artifact (version 1). Optionally compute checksum from data."""
    checksum = _compute_checksum(data) if data else None
    storage_path = _build_storage_path(workspace_id, artifact_in.name, 1)

    artifact = Artifact(
        workspace_id=workspace_id,
        name=artifact_in.name,
        content_type=artifact_in.content_type,
        storage_path=storage_path,
        size_bytes=len(data) if data else 0,
        checksum=checksum,
        artifact_metadata=artifact_in.metadata,
        version=1,
    )
    db.add(artifact)
    await db.flush()
    await db.refresh(artifact)
    return artifact


async def get_artifact_by_id(db: AsyncSession, artifact_id: UUID) -> Artifact | None:
    result = await db.execute(
        select(Artifact).where(Artifact.id == artifact_id, Artifact.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def list_workspace_artifacts(
    db: AsyncSession,
    workspace_id: UUID,
    page: int = 1,
    page_size: int = 50,
    content_type: str | None = None,
) -> tuple[list[Artifact], int]:
    offset = (page - 1) * page_size
    conditions = [Artifact.workspace_id == workspace_id, Artifact.deleted_at.is_(None)]
    if content_type:
        conditions.append(Artifact.content_type == content_type)

    count_result = await db.execute(
        select(func.count(Artifact.id)).where(*conditions)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Artifact)
        .where(*conditions)
        .order_by(Artifact.created_at.desc())
        .offset(offset).limit(page_size)
    )
    return list(result.scalars().all()), total


async def update_artifact(
    db: AsyncSession, artifact: Artifact, artifact_in: ArtifactUpdate, data: bytes | None = None
) -> Artifact:
    """Update artifact metadata. If data provided, creates new version."""
    update_data = artifact_in.model_dump(exclude_unset=True)
    update_data.pop("metadata", None)  # handled separately

    for field, value in update_data.items():
        setattr(artifact, field, value)

    if artifact_in.metadata is not None:
        artifact.artifact_metadata = artifact_in.metadata

    if data:
        artifact.version += 1
        artifact.size_bytes = len(data)
        artifact.checksum = _compute_checksum(data)
        artifact.storage_path = _build_storage_path(
            artifact.workspace_id, artifact.name, artifact.version
        )

    await db.flush()
    await db.refresh(artifact)
    return artifact


async def delete_artifact(db: AsyncSession, artifact: Artifact) -> None:
    artifact.deleted_at = datetime.now(timezone.utc)
    await db.flush()
