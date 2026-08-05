"""Workspace API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
    WorkspaceMemberResponse,
    WorkspaceMemberAdd,
    WorkspaceMemberUpdate,
)
from app.models.user import User
from app.models.workspace import Workspace, MembershipRole, WorkspaceMember
from app.services import workspace_service
from app.services.auth_service import get_user_by_id

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


# ─── Dependency: get workspace by ID with access check ────


async def get_workspace_or_404(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Workspace:
    """Get a workspace and verify the user has access."""
    workspace = await workspace_service.get_workspace_by_id(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    # Check membership
    membership = await workspace_service.get_workspace_membership(
        db, current_user.id, workspace_id
    )
    if membership is None and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return workspace


def require_workspace_role(required_role: MembershipRole):
    """Dependency factory: require a minimum role in a workspace."""
    role_hierarchy = {
        MembershipRole.VIEWER: 0,
        MembershipRole.MEMBER: 1,
        MembershipRole.ADMIN: 2,
        MembershipRole.OWNER: 3,
    }

    async def _check_role(
        workspace: Workspace = Depends(get_workspace_or_404),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> Workspace:
        # Superusers bypass role checks
        if current_user.is_superuser:
            return workspace

        membership = await workspace_service.get_workspace_membership(
            db, current_user.id, workspace.id
        )
        if membership is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        if role_hierarchy.get(membership.role, -1) < role_hierarchy.get(required_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least {required_role.value} role",
            )
        return workspace

    return _check_role


# ─── Workspace CRUD ───────────────────────────────────────


@router.get("", response_model=list[WorkspaceResponse])
@router.get("/", response_model=list[WorkspaceResponse])
async def list_workspaces(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all workspaces the current user has access to."""
    workspaces, total = await workspace_service.list_user_workspaces(
        db, current_user, page=page, page_size=page_size
    )

    # Build responses (member_count already populated by service via subquery)
    responses = []
    for ws in workspaces:
        resp = WorkspaceResponse.model_validate(ws)
        resp.member_count = getattr(ws, 'member_count', 0)
        responses.append(resp)

    return responses


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    workspace_in: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new workspace."""
    try:
        workspace = await workspace_service.create_workspace(db, workspace_in, current_user)
        return WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            description=workspace.description,
            owner_id=workspace.owner_id,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
            member_count=1,
        )
    except workspace_service.WorkspaceSlugTakenError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
@router.get("/{workspace_id}/", response_model=WorkspaceResponse)
async def get_workspace(
    workspace: Workspace = Depends(get_workspace_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get workspace details."""
    count = await workspace_service.get_member_count(db, workspace.id)
    resp = WorkspaceResponse.model_validate(workspace)
    resp.member_count = count
    membership = await workspace_service.get_workspace_membership(
        db, current_user.id, workspace.id
    )
    resp.role = membership.get("role") if membership else None
    return resp


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
@router.patch("/{workspace_id}/", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_in: WorkspaceUpdate,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Update a workspace (Admin+ required)."""
    workspace = await workspace_service.update_workspace(db, workspace, workspace_in)
    count = await workspace_service.get_member_count(db, workspace.id)
    resp = WorkspaceResponse.model_validate(workspace)
    resp.member_count = count
    return resp


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/{workspace_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    """Delete a workspace (Owner only)."""
    await workspace_service.delete_workspace(db, workspace)
    return None


# ─── Membership Management ────────────────────────────────


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
@router.get("/{workspace_id}/members/", response_model=list[WorkspaceMemberResponse])
async def list_members(
    workspace: Workspace = Depends(get_workspace_or_404),
    db: AsyncSession = Depends(get_db),
):
    """List all members of a workspace."""
    members = await workspace_service.list_members(db, workspace)
    return [WorkspaceMemberResponse(**m) for m in members]


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    member_in: WorkspaceMemberAdd,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Add a member to a workspace (Admin+)."""
    try:
        membership = await workspace_service.add_member(db, workspace, member_in)
        # Get user details for response
        user = get_user_by_id(db, member_in.user_id)
        return WorkspaceMemberResponse(
            id=membership.id,
            user_id=membership.user_id,
            role=membership.role,
            username=user.username if user else "",
            email=user.email if user else "",
            created_at=membership.created_at,
        )
    except workspace_service.WorkspaceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.patch("/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberResponse)
async def update_member_role(
    user_id: UUID,
    member_in: WorkspaceMemberUpdate,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Update a member's role (Admin+). Cannot change the owner's role."""
    try:
        membership = await workspace_service.update_member_role(
            db, workspace, user_id, member_in.role
        )
        user = get_user_by_id(db, user_id)
        return WorkspaceMemberResponse(
            id=membership.id,
            user_id=membership.user_id,
            role=membership.role,
            username=user.username if user else "",
            email=user.email if user else "",
            created_at=membership.created_at,
        )
    except workspace_service.MembershipNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    except workspace_service.WorkspaceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: UUID,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from a workspace (Admin+). Cannot remove the owner."""
    try:
        await workspace_service.remove_member(db, workspace, user_id)
        return None
    except workspace_service.MembershipNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    except workspace_service.WorkspaceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
