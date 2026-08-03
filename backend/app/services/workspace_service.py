"""Workspace service - CRUD, membership management, slug generation (Firestore)."""

import re

from app.core.db import FirestoreDB, now_iso, stamp
from app.models.workspace import MembershipRole
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceMemberAdd
from app.services import auth_service

WORKSPACES = "workspaces"
MEMBERS = "workspace_members"


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


def ensure_unique_slug(db: FirestoreDB, slug: str, exclude_id: str | None = None) -> str:
    """Ensure a slug is unique by appending a suffix if needed."""
    original_slug = slug
    counter = 0
    while True:
        existing = None
        for row in db.query(WORKSPACES, "slug", slug):
            if not row.get("deleted_at"):
                existing = row
                break
        if existing is None:
            return slug
        if exclude_id and existing["id"] == exclude_id:
            return slug
        counter += 1
        slug = f"{original_slug}-{counter}"


async def get_workspace_membership(
    db: FirestoreDB, user_id: str, workspace_id: str
) -> dict | None:
    """Get a user's membership in a workspace."""
    for row in db.query(MEMBERS, "workspace_id", str(workspace_id)):
        if str(row.get("user_id") or "") == str(user_id):
            return row
    return None


# ─── CRUD Operations ─────────────────────────────────


async def create_workspace(
    db: FirestoreDB, workspace_in: WorkspaceCreate, owner: dict
) -> dict:
    """Create a new workspace and add the owner as an OWNER member."""
    slug = ensure_unique_slug(db, workspace_in.slug or generate_slug(workspace_in.name))

    workspace = stamp({
        "name": workspace_in.name,
        "slug": slug,
        "description": workspace_in.description,
        "owner_id": owner["id"],
        "settings": None,
        "member_count": 1,
    })
    db.add(WORKSPACES, workspace)

    membership = stamp({
        "workspace_id": workspace["id"],
        "user_id": owner["id"],
        "role": MembershipRole.OWNER.value,
    })
    db.add(MEMBERS, membership)

    return workspace


async def get_workspace_by_id(db: FirestoreDB, workspace_id: str) -> dict | None:
    """Get a workspace by ID."""
    workspace = db.get(WORKSPACES, str(workspace_id))
    if workspace is None or workspace.get("deleted_at"):
        return None
    workspace["member_count"] = _member_count(db, workspace["id"])
    return workspace


async def get_workspace_by_slug(db: FirestoreDB, slug: str) -> dict | None:
    """Get a workspace by slug."""
    for row in db.query(WORKSPACES, "slug", slug):
        if not row.get("deleted_at"):
            row["member_count"] = _member_count(db, row["id"])
            return row
    return None


def _member_count(db: FirestoreDB, workspace_id: str) -> int:
    return len(db.query(MEMBERS, "workspace_id", workspace_id))


async def list_user_workspaces(
    db: FirestoreDB, user: dict, page: int = 1, page_size: int = 50
) -> tuple[list[dict], int]:
    """List all workspaces the user has access to."""
    member_rows = db.query(MEMBERS, "user_id", user["id"])
    ws_ids = {str(r["workspace_id"]) for r in member_rows}

    rows = [r for r in db.query(WORKSPACES) if not r.get("deleted_at") and r["id"] in ws_ids]
    rows.sort(key=lambda r: (r.get("updated_at") or "", r.get("created_at") or ""), reverse=True)
    for r in rows:
        r["member_count"] = _member_count(db, r["id"])

    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def update_workspace(
    db: FirestoreDB, workspace: dict, workspace_in: WorkspaceUpdate
) -> dict:
    """Update a workspace."""
    update_data = workspace_in.model_dump(exclude_unset=True)

    if "slug" in update_data and update_data["slug"] != workspace["slug"]:
        update_data["slug"] = ensure_unique_slug(db, update_data["slug"], exclude_id=workspace["id"])

    for field, value in update_data.items():
        workspace[field] = value

    db.set(WORKSPACES, workspace["id"], workspace)
    return workspace


async def delete_workspace(db: FirestoreDB, workspace: dict) -> None:
    """Soft-delete a workspace."""
    workspace["deleted_at"] = now_iso()
    db.set(WORKSPACES, workspace["id"], workspace)


# ─── Membership Operations ───────────────────────────


async def add_member(
    db: FirestoreDB, workspace: dict, member_in: WorkspaceMemberAdd
) -> dict:
    """Add a member to a workspace."""
    user = auth_service.get_user_by_id(db, member_in.user_id)
    if user is None:
        raise WorkspaceError("User not found", status_code=404)

    existing = await get_workspace_membership(db, member_in.user_id, workspace["id"])
    if existing:
        raise WorkspaceError("User is already a member of this workspace", status_code=409)

    membership = stamp({
        "workspace_id": workspace["id"],
        "user_id": str(member_in.user_id),
        "role": member_in.role.value,
    })
    db.add(MEMBERS, membership)
    return membership


async def update_member_role(
    db: FirestoreDB,
    workspace: dict,
    user_id: str,
    new_role: MembershipRole,
) -> dict:
    """Update a member's role in a workspace."""
    membership = await get_workspace_membership(db, user_id, workspace["id"])
    if membership is None:
        raise MembershipNotFoundError()

    if membership.get("role") == MembershipRole.OWNER.value:
        raise WorkspaceError("Cannot change the owner's role", status_code=400)

    membership["role"] = new_role.value
    db.set(MEMBERS, membership["id"], membership)
    return membership


async def remove_member(db: FirestoreDB, workspace: dict, user_id: str) -> None:
    """Remove a member from a workspace."""
    membership = await get_workspace_membership(db, user_id, workspace["id"])
    if membership is None:
        raise MembershipNotFoundError()

    if membership.get("role") == MembershipRole.OWNER.value:
        raise WorkspaceError("Cannot remove the workspace owner", status_code=400)

    db.delete(MEMBERS, membership["id"])


async def list_members(db: FirestoreDB, workspace: dict) -> list[dict]:
    """List all members of a workspace with user details."""
    rows = db.query(MEMBERS, "workspace_id", workspace["id"])
    rows.sort(key=lambda r: r.get("created_at") or "")

    members = []
    for member in rows:
        user = auth_service.get_user_by_id(db, member["user_id"]) or {}
        members.append({
            "id": member["id"],
            "user_id": member["user_id"],
            "role": member["role"],
            "username": user.get("username", ""),
            "email": user.get("email", ""),
            "created_at": member["created_at"],
        })
    return members


async def get_member_count(db: FirestoreDB, workspace_id: str) -> int:
    """Get the number of members in a workspace."""
    return len(db.query(MEMBERS, "workspace_id", str(workspace_id)))
