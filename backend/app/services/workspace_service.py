"""Workspace service - CRUD, membership management, slug generation."""

import re
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.workspace import Workspace, WorkspaceMember, MembershipRole
from app.models.user import User
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceMemberAdd


class WorkspaceError(Exception):
    """Base workspace error."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class WorkspaceNotFoundError(WorkspaceError):
    def __init__(self):
        super().__init__("Workspace not found", status_code=404)


class WorkspaceAccessDeniedError(WorkspaceError):
    def __init__(self):
        super().__init__("Access denied to this workspace", status_code=403)


class WorkspaceSlugTakenError(WorkspaceError):
    def __init__(self):
        super().__init__("This workspace slug is already taken", status_code=409)


class MembershipNotFoundError(WorkspaceError):
    def __init__(self):
        super().__init__("User is not a member of this workspace", status_code=404)


# ─── Helpers ──────────────────────────────────────────


def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a workspace name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9-]", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug[:128] or "workspace"


async def ensure_unique_slug(db: AsyncSession, slug: str, exclude_id: UUID | None = None) -> str:
    """Ensure a slug is unique by appending a suffix if needed."""
    original_slug = slug
    counter = 0
    while True:
        result = await db.execute(
            select(Workspace).where(Workspace.slug == slug, Workspace.deleted_at.is_(None))
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            return slug
        if exclude_id and existing.id == exclude_id:
            return slug
        counter += 1
        slug = f"{original_slug}-{counter}"


async def get_workspace_membership(
    db: AsyncSession, user_id: UUID, workspace_id: UUID
) -> WorkspaceMember | None:
    """Get a user's membership in a workspace."""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


# ─── CRUD Operations ─────────────────────────────────


async def create_workspace(
    db: AsyncSession, workspace_in: WorkspaceCreate, owner: User
) -> Workspace:
    """Create a new workspace and add the owner as an OWNER member."""
    slug = await ensure_unique_slug(db, workspace_in.slug or generate_slug(workspace_in.name))

    workspace = Workspace(
        name=workspace_in.name,
        slug=slug,
        description=workspace_in.description,
        owner_id=owner.id,
    )
    db.add(workspace)
    await db.flush()
    await db.refresh(workspace)

    # Add owner as member with OWNER role
    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=owner.id,
        role=MembershipRole.OWNER,
    )
    db.add(membership)
    await db.flush()

    return workspace


async def get_workspace_by_id(db: AsyncSession, workspace_id: UUID) -> Workspace | None:
    """Get a workspace by ID."""
    result = await db.execute(
        select(Workspace)
        .where(Workspace.id == workspace_id, Workspace.deleted_at.is_(None))
        .options(selectinload(Workspace.members))
    )
    return result.scalar_one_or_none()


async def get_workspace_by_slug(db: AsyncSession, slug: str) -> Workspace | None:
    """Get a workspace by slug."""
    result = await db.execute(
        select(Workspace)
        .where(Workspace.slug == slug, Workspace.deleted_at.is_(None))
        .options(selectinload(Workspace.members))
    )
    return result.scalar_one_or_none()


async def list_user_workspaces(
    db: AsyncSession, user: User, page: int = 1, page_size: int = 50
) -> tuple[list[Workspace], int]:
    """List all workspaces the user has access to."""
    offset = (page - 1) * page_size

    # Subquery: workspace IDs where user is a member
    member_subq = (
        select(WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == user.id)
        .subquery()
    )

    # Subquery: member count per workspace
    count_subq = (
        select(
            WorkspaceMember.workspace_id.label("ws_id"),
            func.count(WorkspaceMember.id).label("cnt"),
        )
        .group_by(WorkspaceMember.workspace_id)
        .subquery()
    )

    # Count total
    count_result = await db.execute(
        select(func.count(Workspace.id)).where(
            Workspace.id.in_(select(member_subq.c.workspace_id)),
            Workspace.deleted_at.is_(None),
        )
    )
    total = count_result.scalar() or 0

    # Fetch workspaces with member count in one query
    result = await db.execute(
        select(Workspace, count_subq.c.cnt)
        .outerjoin(count_subq, Workspace.id == count_subq.c.ws_id)
        .where(
            Workspace.id.in_(select(member_subq.c.workspace_id)),
            Workspace.deleted_at.is_(None),
        )
        .order_by(Workspace.updated_at.desc().nulls_last(), Workspace.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()

    workspaces = []
    for ws, cnt in rows:
        ws.member_count = cnt or 0
        workspaces.append(ws)

    return workspaces, total


async def update_workspace(
    db: AsyncSession, workspace: Workspace, workspace_in: WorkspaceUpdate
) -> Workspace:
    """Update a workspace."""
    update_data = workspace_in.model_dump(exclude_unset=True)

    if "slug" in update_data and update_data["slug"] != workspace.slug:
        update_data["slug"] = await ensure_unique_slug(
            db, update_data["slug"], exclude_id=workspace.id
        )

    for field, value in update_data.items():
        setattr(workspace, field, value)

    await db.flush()
    await db.refresh(workspace)
    return workspace


async def delete_workspace(db: AsyncSession, workspace: Workspace) -> None:
    """Soft-delete a workspace."""
    workspace.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ─── Membership Operations ───────────────────────────


async def add_member(
    db: AsyncSession, workspace: Workspace, member_in: WorkspaceMemberAdd
) -> WorkspaceMember:
    """Add a member to a workspace."""
    # Validate the target user exists (SQLite does not enforce FKs by default,
    # so we check explicitly to keep behavior consistent across databases)
    result = await db.execute(
        select(User).where(User.id == member_in.user_id, User.deleted_at.is_(None))
    )
    if result.scalar_one_or_none() is None:
        raise WorkspaceError("User not found", status_code=404)

    # Check if already a member
    existing = await get_workspace_membership(db, member_in.user_id, workspace.id)
    if existing:
        raise WorkspaceError("User is already a member of this workspace", status_code=409)

    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=member_in.user_id,
        role=member_in.role,
    )
    db.add(membership)
    await db.flush()
    await db.refresh(membership)
    return membership


async def update_member_role(
    db: AsyncSession,
    workspace: Workspace,
    user_id: UUID,
    new_role: MembershipRole,
) -> WorkspaceMember:
    """Update a member's role in a workspace."""
    membership = await get_workspace_membership(db, user_id, workspace.id)
    if membership is None:
        raise MembershipNotFoundError()

    if membership.role == MembershipRole.OWNER:
        raise WorkspaceError("Cannot change the owner's role", status_code=400)

    membership.role = new_role
    await db.flush()
    await db.refresh(membership)
    return membership


async def remove_member(db: AsyncSession, workspace: Workspace, user_id: UUID) -> None:
    """Remove a member from a workspace."""
    membership = await get_workspace_membership(db, user_id, workspace.id)
    if membership is None:
        raise MembershipNotFoundError()

    if membership.role == MembershipRole.OWNER:
        raise WorkspaceError("Cannot remove the workspace owner", status_code=400)

    await db.delete(membership)
    await db.flush()


async def list_members(
    db: AsyncSession, workspace: Workspace
) -> list[dict]:
    """List all members of a workspace with user details."""
    result = await db.execute(
        select(WorkspaceMember, User)
        .join(User, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == workspace.id)
        .order_by(WorkspaceMember.created_at.asc())
    )
    rows = result.all()

    members = []
    for member, user in rows:
        members.append({
            "id": member.id,
            "user_id": member.user_id,
            "role": member.role,
            "username": user.username,
            "email": user.email,
            "created_at": member.created_at,
        })
    return members


async def get_member_count(db: AsyncSession, workspace_id: UUID) -> int:
    """Get the number of members in a workspace."""
    result = await db.execute(
        select(func.count(WorkspaceMember.id)).where(
            WorkspaceMember.workspace_id == workspace_id
        )
    )
    return result.scalar() or 0
