"""Execution Graph API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404
from app.schemas.execution_graph import (
    ExecutionGraphNodeResponse,
    ExecutionGraphResponse,
)
from app.models.user import User
from app.models.workspace import Workspace
from app.services import execution_graph_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/executions/{execution_id}",
    tags=["Execution Graph"],
)


@router.get("/graph", response_model=ExecutionGraphResponse)
async def get_execution_graph(
    execution_id: UUID,
    workspace: Workspace = Depends(get_workspace_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Get the full execution graph with all nodes and summary stats."""
    nodes, stats = await execution_graph_service.get_execution_graph(db, execution_id)
    return ExecutionGraphResponse(
        nodes=[ExecutionGraphNodeResponse.model_validate(n) for n in nodes],
        total_duration_ms=stats["total_duration_ms"],
        total_cost_usd=stats["total_cost_usd"],
        total_tokens=stats["total_tokens"],
    )


@router.get("/graph/nodes", response_model=list[ExecutionGraphNodeResponse])
async def list_execution_nodes(
    execution_id: UUID,
    workspace: Workspace = Depends(get_workspace_or_404),
    db: AsyncSession = Depends(get_db),
):
    """List all nodes in an execution graph."""
    nodes = await execution_graph_service.list_execution_nodes(db, execution_id)
    return [ExecutionGraphNodeResponse.model_validate(n) for n in nodes]


@router.get("/graph/nodes/{node_id}", response_model=ExecutionGraphNodeResponse)
async def get_execution_node(
    execution_id: UUID,
    node_id: UUID,
    workspace: Workspace = Depends(get_workspace_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific execution graph node."""
    node = await execution_graph_service.get_node_by_id(db, node_id)
    if node is None or str(node.execution_id) != str(execution_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return ExecutionGraphNodeResponse.model_validate(node)
