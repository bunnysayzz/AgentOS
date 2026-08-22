"""Secrets Manager API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import FirestoreDB
from app.core.database import get_db
from app.api.workspaces import get_workspace_or_404, require_workspace_role
from app.schemas.secret import SecretCreate, SecretUpdate, SecretResponse
from app.models.workspace import Workspace, MembershipRole
from app.services import secret_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/secrets",
    tags=["Secrets"],
)


@router.get("", response_model=list[SecretResponse])
@router.get("/", response_model=list[SecretResponse])
async def list_secrets(
    workspace: Workspace = Depends(get_workspace_or_404),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: FirestoreDB = Depends(get_db),
):
    """List secrets in a workspace. Values are NEVER returned."""
    secrets, total = await secret_service.list_workspace_secrets(
        db, workspace.id, page=page, page_size=page_size
    )
    return [SecretResponse.model_validate(s) for s in secrets]


@router.post("", response_model=SecretResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SecretResponse, status_code=status.HTTP_201_CREATED)
async def create_secret(
    secret_in: SecretCreate,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: FirestoreDB = Depends(get_db),
):
    """Create a secret. The value is encrypted at rest and NEVER returned."""
    try:
        secret = await secret_service.create_secret(db, workspace.id, secret_in)
        return SecretResponse.model_validate(secret)
    except secret_service.SecretSlugTakenError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.get("/{secret_id}", response_model=SecretResponse)
async def get_secret(
    secret_id: UUID,
    workspace: Workspace = Depends(get_workspace_or_404),
    db: FirestoreDB = Depends(get_db),
):
    """Get secret metadata. Value is NEVER returned."""
    secret = await secret_service.get_secret_by_id(db, secret_id)
    if secret is None or secret.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found")
    return SecretResponse.model_validate(secret)


@router.patch("/{secret_id}", response_model=SecretResponse)
async def update_secret(
    secret_id: UUID,
    secret_in: SecretUpdate,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: FirestoreDB = Depends(get_db),
):
    """Update a secret. Value is re-encrypted and NEVER returned."""
    secret = await secret_service.get_secret_by_id(db, secret_id)
    if secret is None or secret.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found")

    secret = await secret_service.update_secret(db, secret, secret_in)
    return SecretResponse.model_validate(secret)


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    secret_id: UUID,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: FirestoreDB = Depends(get_db),
):
    """Soft-delete a secret (Admin+)."""
    secret = await secret_service.get_secret_by_id(db, secret_id)
    if secret is None or secret.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found")
    await secret_service.delete_secret(db, secret)
    return None
