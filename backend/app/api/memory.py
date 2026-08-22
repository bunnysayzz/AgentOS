"""Memory Engine API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import FirestoreDB
from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404, require_workspace_role
from app.schemas.memory import MemoryEntryCreate, MemoryEntryResponse
from app.models.user import User
from app.models.workspace import Workspace, MembershipRole
from app.services import memory_service

router = APIRouter(tags=["Memory"])


@router.get(
    "/workspaces/{workspace_id}/memory",
    response_model=list[MemoryEntryResponse],
)
async def list_memory(
    workspace: Workspace = Depends(get_workspace_or_404),
    agent_id: UUID | None = Query(None),
    memory_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: FirestoreDB = Depends(get_db),
):
    """List memory entries in a workspace."""
    entries = await memory_service.list_workspace_memory(
        db, workspace.id, agent_id=agent_id, memory_type=memory_type, limit=limit
    )
    return [MemoryEntryResponse.model_validate(e) for e in entries]


@router.post(
    "/workspaces/{workspace_id}/memory",
    response_model=MemoryEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def store_memory(
    entry_in: MemoryEntryCreate,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    agent_id: UUID | None = Query(None),
    db: FirestoreDB = Depends(get_db),
):
    """Store a memory entry (Member+)."""
    entry = await memory_service.create_entry(
        db, entry_in, workspace_id=workspace.id, agent_id=agent_id
    )
    return MemoryEntryResponse.model_validate(entry)


@router.get(
    "/workspaces/{workspace_id}/memory/sessions/{session_id}",
    response_model=list[MemoryEntryResponse],
)
async def get_session_memory(
    session_id: str,
    workspace: Workspace = Depends(get_workspace_or_404),
    agent_id: UUID | None = Query(None),
    db: FirestoreDB = Depends(get_db),
):
    """Get all memory for a conversation session."""
    entries = await memory_service.list_session_memory(
        db, session_id, agent_id=agent_id
    )
    return [MemoryEntryResponse.model_validate(e) for e in entries]


@router.get(
    "/workspaces/{workspace_id}/memory/search",
    response_model=list[MemoryEntryResponse],
)
async def search_memory(
    q: str = Query(..., min_length=1),
    workspace: Workspace = Depends(get_workspace_or_404),
    agent_id: UUID | None = Query(None),
    memory_type: str | None = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db: FirestoreDB = Depends(get_db),
):
    """Search memory entries by keyword."""
    entries = await memory_service.search_memory(
        db, q, workspace_id=workspace.id, agent_id=agent_id,
        memory_type=memory_type, limit=limit,
    )
    return [MemoryEntryResponse.model_validate(e) for e in entries]


@router.delete(
    "/workspaces/{workspace_id}/memory/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
)
async def clear_session_memory(
    session_id: str,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.MEMBER)),
    db: FirestoreDB = Depends(get_db),
):
    """Clear all memory for a session (Member+)."""
    count = await memory_service.clear_session(db, session_id)
    return {"deleted": count, "session_id": session_id}


@router.post(
    "/workspaces/{workspace_id}/memory/consolidate",
    status_code=status.HTTP_200_OK,
)
async def consolidate_memory(
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    session_id: str | None = Query(None),
    agent_id: UUID | None = Query(None),
    max_entries: int = Query(50, ge=10, le=1000),
    db: FirestoreDB = Depends(get_db),
):
    """Consolidate memory (Admin+). Trims old entries beyond max_entries."""
    if session_id:
        count = await memory_service.consolidate_session_memory(
            db, session_id, agent_id=agent_id, max_entries=max_entries
        )
    else:
        count = await memory_service.consolidate_workspace_memory(
            db, workspace.id, max_entries=max_entries
        )
    return {"consolidated": count}


@router.get(
    "/memory/{entry_id}",
    response_model=MemoryEntryResponse,
)
async def get_memory_entry(
    entry_id: UUID,
    db: FirestoreDB = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific memory entry."""
    entry = await memory_service.get_entry(db, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory entry not found")
    return MemoryEntryResponse.model_validate(entry)


@router.delete(
    "/memory/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_memory_entry(
    entry_id: UUID,
    db: FirestoreDB = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a specific memory entry."""
    entry = await memory_service.get_entry(db, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory entry not found")
    await memory_service.delete_entry(db, entry)
    return None
