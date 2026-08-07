"""Public agent gallery — browse and clone published community agents.

The gallery is the one public, unauthenticated surface of the API: anyone
(including guests) can browse published agents, and a signed-in user can
clone one into their workspace with a single call.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.schemas.agent import AgentResponse
from app.schemas.workspace import WorkspaceCreate
from app.services import agent_service, workspace_service

router = APIRouter(prefix="/gallery", tags=["Gallery"])


class GalleryAgentResponse(BaseModel):
    """Public view of a published agent (never includes secrets)."""

    id: UUID
    name: str
    description: str | None
    system_prompt: str | None
    model_provider: str
    model_name: str
    temperature: float
    max_tokens: int
    status: str
    author_username: str
    workspace_name: str
    tool_count: int = 0
    published_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[GalleryAgentResponse])
@router.get("/", response_model=list[GalleryAgentResponse])
async def list_gallery(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=48),
    db=Depends(get_db),
):
    """Public: list published agents, newest first."""
    agents, total = await agent_service.list_published_agents(
        db, page=page, page_size=page_size
    )
    return [GalleryAgentResponse.model_validate(a) for a in agents]


@router.get("/{agent_id}", response_model=GalleryAgentResponse)
async def get_gallery_agent(agent_id: UUID, db=Depends(get_db)):
    """Public: get a single published agent."""
    agent = await agent_service.get_published_agent_by_id(db, str(agent_id))
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or not published",
        )
    return GalleryAgentResponse.model_validate(agent)


@router.post("/{agent_id}/clone", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def clone_gallery_agent(
    agent_id: UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Clone a published agent into the caller's workspace (auth required)."""
    source = await agent_service.get_published_agent_by_id(db, str(agent_id))
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or not published",
        )

    # Target workspace: the user's first workspace, or a fresh "Personal"
    # workspace when they don't have one yet.
    workspaces, _ = await workspace_service.list_user_workspaces(
        db, current_user, page=1, page_size=1
    )
    if workspaces:
        target = workspaces[0]
    else:
        target = await workspace_service.create_workspace(
            db, WorkspaceCreate(name="Personal"), current_user
        )

    agent = await agent_service.clone_agent(db, source, target["id"])
    return AgentResponse.model_validate(agent)
