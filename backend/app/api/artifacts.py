"""Artifact Store API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import FirestoreDB
from app.core.database import get_db
from app.api.workspaces import get_workspace_or_404, require_workspace_role
from app.schemas.artifact import ArtifactCreate, ArtifactUpdate, ArtifactResponse
from app.models.workspace import Workspace, MembershipRole
from app.services import artifact_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/artifacts",
    tags=["Artifacts"],
)


@router.get("", response_model=list[ArtifactResponse])
@router.get("/", response_model=list[ArtifactResponse])
async def list_artifacts(
    workspace: Workspace = Depends(get_workspace_or_404),
    content_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: FirestoreDB = Depends(get_db),
):
    """List artifacts in a workspace, optionally filtered by content type."""
    artifacts, total = await artifact_service.list_workspace_artifacts(
        db, workspace.id, page=page, page_size=page_size, content_type=content_type
    )
    return [ArtifactResponse.model_validate(a) for a in artifacts]


@router.post("", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
async def create_artifact(
    artifact_in: ArtifactCreate,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: FirestoreDB = Depends(get_db),
):
    """Register a new artifact."""
    artifact = await artifact_service.create_artifact(db, workspace.id, artifact_in)
    return ArtifactResponse.model_validate(artifact)


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: UUID,
    workspace: Workspace = Depends(get_workspace_or_404),
    db: FirestoreDB = Depends(get_db),
):
    """Get artifact metadata."""
    artifact = await artifact_service.get_artifact_by_id(db, artifact_id)
    if artifact is None or artifact.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return ArtifactResponse.model_validate(artifact)


@router.patch("/{artifact_id}", response_model=ArtifactResponse)
async def update_artifact(
    artifact_id: UUID,
    artifact_in: ArtifactUpdate,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: FirestoreDB = Depends(get_db),
):
    """Update artifact metadata."""
    artifact = await artifact_service.get_artifact_by_id(db, artifact_id)
    if artifact is None or artifact.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    artifact = await artifact_service.update_artifact(db, artifact, artifact_in)
    return ArtifactResponse.model_validate(artifact)


@router.delete("/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artifact(
    artifact_id: UUID,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: FirestoreDB = Depends(get_db),
):
    """Soft-delete an artifact."""
    artifact = await artifact_service.get_artifact_by_id(db, artifact_id)
    if artifact is None or artifact.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    await artifact_service.delete_artifact(db, artifact)
    return None
