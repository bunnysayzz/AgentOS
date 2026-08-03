"""Artifact Store service — versioned asset tracking (Firestore-backed)."""

import hashlib

from app.core.db import FirestoreDB, now_iso, stamp
from app.schemas.artifact import ArtifactCreate, ArtifactUpdate

ARTIFACTS = "artifacts"


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


def _build_storage_path(workspace_id: str, name: str, version: int) -> str:
    """Build a deterministic storage path for an artifact."""
    sanitized = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    return f"workspaces/{workspace_id}/artifacts/{sanitized}/v{version}"


# ─── CRUD ────────────────────────────────────────────


async def create_artifact(
    db: FirestoreDB,
    workspace_id: str,
    artifact_in: ArtifactCreate,
    data: bytes | None = None,
) -> dict:
    """Register a new artifact (version 1). Optionally compute checksum from data."""
    checksum = _compute_checksum(data) if data else None
    artifact = stamp({
        "workspace_id": str(workspace_id),
        "name": artifact_in.name,
        "content_type": artifact_in.content_type,
        "storage_path": _build_storage_path(str(workspace_id), artifact_in.name, 1),
        "size_bytes": len(data) if data else 0,
        "checksum": checksum,
        "artifact_metadata": artifact_in.metadata,
        "version": 1,
    })
    db.add(ARTIFACTS, artifact)
    return artifact


async def get_artifact_by_id(db: FirestoreDB, artifact_id: str) -> dict | None:
    artifact = db.get(ARTIFACTS, str(artifact_id))
    if artifact is None or artifact.get("deleted_at"):
        return None
    return artifact


async def list_workspace_artifacts(
    db: FirestoreDB,
    workspace_id: str,
    page: int = 1,
    page_size: int = 50,
    content_type: str | None = None,
) -> tuple[list[dict], int]:
    rows = [
        r for r in db.query(ARTIFACTS, "workspace_id", str(workspace_id))
        if not r.get("deleted_at")
        and (content_type is None or r.get("content_type") == content_type)
    ]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def update_artifact(
    db: FirestoreDB, artifact: dict, artifact_in: ArtifactUpdate, data: bytes | None = None
) -> dict:
    """Update artifact metadata. If data provided, creates new version."""
    update_data = artifact_in.model_dump(exclude_unset=True)
    update_data.pop("metadata", None)  # handled separately

    for field, value in update_data.items():
        artifact[field] = value

    if artifact_in.metadata is not None:
        artifact["artifact_metadata"] = artifact_in.metadata

    if data:
        artifact["version"] = (artifact.get("version") or 1) + 1
        artifact["size_bytes"] = len(data)
        artifact["checksum"] = _compute_checksum(data)
        artifact["storage_path"] = _build_storage_path(
            artifact["workspace_id"], artifact["name"], artifact["version"]
        )

    db.set(ARTIFACTS, artifact["id"], artifact)
    return artifact


async def delete_artifact(db: FirestoreDB, artifact: dict) -> None:
    artifact["deleted_at"] = now_iso()
    db.set(ARTIFACTS, artifact["id"], artifact)
