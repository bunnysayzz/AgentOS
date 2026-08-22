"""Tool Registry API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import FirestoreDB
from app.core.database import get_db
from app.api.deps import get_current_active_user, require_superuser
from app.api.workspaces import get_workspace_or_404, require_workspace_role
from app.schemas.tool import (
    ToolCreate,
    ToolUpdate,
    ToolResponse,
    ToolExecutionResponse,
)
from app.models.user import User
from app.models.workspace import Workspace, MembershipRole
from app.models.tool import Tool
from app.services import tool_service

router = APIRouter(tags=["Tools"], redirect_slashes=False)


# ─── Dependency ─────────────────────────────────────


async def get_tool_or_404(
    tool_id: UUID,
    db: FirestoreDB = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Tool:
    """Get a tool and verify the user has access."""
    tool = await tool_service.get_tool_by_id(db, tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    # Allow access if: public tool, same workspace, or superuser
    if tool.is_public or current_user.is_superuser:
        return tool

    if tool.workspace_id:
        # Check workspace membership
        from app.services import workspace_service
        membership = await workspace_service.get_workspace_membership(
            db, current_user.id, tool.workspace_id
        )
        if membership is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return tool


# ─── Workspace Tools ────────────────────────────────


@router.get(
    "/workspaces/{workspace_id}/tools",
    response_model=list[ToolResponse],
)
@router.get(
    "/workspaces/{workspace_id}/tools/",
    response_model=list[ToolResponse],
)
async def list_tools(
    workspace: Workspace = Depends(get_workspace_or_404),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: FirestoreDB = Depends(get_db),
):
    """List tools available in a workspace (own + public)."""
    tools, total = await tool_service.list_workspace_tools(
        db, workspace.id, page=page, page_size=page_size
    )
    return [ToolResponse.model_validate(t) for t in tools]


@router.post(
    "/workspaces/{workspace_id}/tools",
    response_model=ToolResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/workspaces/{workspace_id}/tools/",
    response_model=ToolResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tool(
    tool_in: ToolCreate,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: FirestoreDB = Depends(get_db),
):
    """Create a new tool in a workspace (Admin+)."""
    try:
        tool = await tool_service.create_tool(db, tool_in, workspace_id=workspace.id)
        return ToolResponse.model_validate(tool)
    except tool_service.ToolSlugTakenError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


# ─── Global Tools (Public + Admin) ──────────────────


@router.get("/tools/public", response_model=list[ToolResponse])
async def list_public_tools(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: FirestoreDB = Depends(get_db),
):
    """List all public/builtin tools."""
    tools, total = await tool_service.list_public_tools(db, page=page, page_size=page_size)
    return [ToolResponse.model_validate(t) for t in tools]


@router.post("/tools", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_global_tool(
    tool_in: ToolCreate,
    db: FirestoreDB = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    """Create a global/public tool (Superuser only)."""
    try:
        tool = await tool_service.create_tool(db, tool_in, workspace_id=None)
        return ToolResponse.model_validate(tool)
    except tool_service.ToolSlugTakenError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


async def require_tool_edit_permission(
    tool: Tool = Depends(get_tool_or_404),
    current_user: User = Depends(get_current_active_user),
    db: FirestoreDB = Depends(get_db),
) -> Tool:
    """Require admin role for workspace tools, superuser for global tools."""
    if tool.workspace_id:
        from app.services import workspace_service
        membership = await workspace_service.get_workspace_membership(
            db, current_user.id, tool.workspace_id
        )
        if not (membership and membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required to modify this tool",
            )
    elif not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser role required to modify global tools",
        )
    return tool


# ─── Single Tool Operations ─────────────────────────


@router.get("/tools/{tool_id}", response_model=ToolResponse)
async def get_tool(tool: Tool = Depends(get_tool_or_404)):
    """Get a tool by ID."""
    return ToolResponse.model_validate(tool)


@router.patch("/tools/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_in: ToolUpdate,
    tool: Tool = Depends(require_tool_edit_permission),
    db: FirestoreDB = Depends(get_db),
):
    """Update a tool."""

    tool = await tool_service.update_tool(db, tool, tool_in)
    return ToolResponse.model_validate(tool)


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool: Tool = Depends(require_tool_edit_permission),
    db: FirestoreDB = Depends(get_db),
):
    """Delete a tool (soft-delete)."""

    await tool_service.delete_tool(db, tool)
    return None


# ─── Tool Executions ────────────────────────────────


@router.get("/tools/{tool_id}/executions", response_model=list[ToolExecutionResponse])
async def list_tool_executions(
    tool: Tool = Depends(get_tool_or_404),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: FirestoreDB = Depends(get_db),
):
    """List executions for a tool."""
    executions, total = await tool_service.list_tool_executions(
        db, tool.id, page=page, page_size=page_size
    )
    return [ToolExecutionResponse.model_validate(e) for e in executions]
