"""Memory Engine service - CRUD, semantic search, session management, consolidation."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import MemoryEntry
from app.schemas.memory import MemoryEntryCreate, MemorySearchQuery


# ─── Errors ──────────────────────────────────────────


class MemoryError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ─── CRUD ──────────────────────────────────────────


async def create_entry(
    db: AsyncSession,
    entry_in: MemoryEntryCreate,
    workspace_id: UUID | None = None,
    agent_id: UUID | None = None,
) -> MemoryEntry:
    """Store a new memory entry."""
    entry = MemoryEntry(
        workspace_id=workspace_id,
        agent_id=agent_id,
        session_id=entry_in.session_id,
        role=entry_in.role,
        content=entry_in.content,
        memory_type=entry_in.memory_type,
        entry_metadata=entry_in.metadata,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def get_entry(db: AsyncSession, entry_id: UUID) -> MemoryEntry | None:
    result = await db.execute(select(MemoryEntry).where(MemoryEntry.id == entry_id))
    return result.scalar_one_or_none()


async def list_session_memory(
    db: AsyncSession,
    session_id: str,
    agent_id: UUID | None = None,
    limit: int = 100,
) -> list[MemoryEntry]:
    """Get all memory entries for a conversation session."""
    conditions = [MemoryEntry.session_id == session_id]
    if agent_id:
        conditions.append(MemoryEntry.agent_id == agent_id)

    result = await db.execute(
        select(MemoryEntry)
        .where(*conditions)
        .order_by(MemoryEntry.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_agent_memory(
    db: AsyncSession,
    agent_id: UUID,
    memory_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[MemoryEntry], int]:
    """List all memory for an agent."""
    offset = (page - 1) * page_size
    conditions = [MemoryEntry.agent_id == agent_id]
    if memory_type:
        conditions.append(MemoryEntry.memory_type == memory_type)

    count_result = await db.execute(select(func.count(MemoryEntry.id)).where(*conditions))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(MemoryEntry)
        .where(*conditions)
        .order_by(MemoryEntry.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def list_workspace_memory(
    db: AsyncSession,
    workspace_id: UUID,
    agent_id: UUID | None = None,
    memory_type: str | None = None,
    limit: int = 50,
) -> list[MemoryEntry]:
    """List memory entries for a workspace."""
    conditions = [MemoryEntry.workspace_id == workspace_id]
    if agent_id:
        conditions.append(MemoryEntry.agent_id == agent_id)
    if memory_type:
        conditions.append(MemoryEntry.memory_type == memory_type)

    result = await db.execute(
        select(MemoryEntry)
        .where(*conditions)
        .order_by(MemoryEntry.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def delete_entry(db: AsyncSession, entry: MemoryEntry) -> None:
    await db.delete(entry)
    await db.flush()


async def clear_session(db: AsyncSession, session_id: str) -> int:
    """Clear all memory for a session. Returns count of deleted entries."""
    result = await db.execute(
        select(MemoryEntry).where(MemoryEntry.session_id == session_id)
    )
    entries = result.scalars().all()
    count = len(entries)
    for entry in entries:
        await db.delete(entry)
    await db.flush()
    return count


# ─── Search ─────────────────────────────────────────


async def search_memory(
    db: AsyncSession,
    query: str,
    workspace_id: UUID | None = None,
    agent_id: UUID | None = None,
    memory_type: str | None = None,
    limit: int = 10,
) -> list[MemoryEntry]:
    """Simple keyword-based memory search (no vector embeddings yet).
    
    In production, this would use a vector store (pgvector, Qdrant, etc.)
    for semantic search. For now, we use LIKE-based text matching.
    """
    conditions = [MemoryEntry.deleted_at.is_(None)]

    # Keyword match on content
    search_terms = query.lower().split()
    keyword_conditions = []
    for term in search_terms:
        keyword_conditions.append(MemoryEntry.content.ilike(f"%{term}%"))
    if keyword_conditions:
        conditions.append(or_(*keyword_conditions))

    if workspace_id:
        conditions.append(MemoryEntry.workspace_id == workspace_id)
    if agent_id:
        conditions.append(MemoryEntry.agent_id == agent_id)
    if memory_type:
        conditions.append(MemoryEntry.memory_type == memory_type)

    result = await db.execute(
        select(MemoryEntry)
        .where(*conditions)
        .order_by(MemoryEntry.importance_score.desc().nulls_last(), MemoryEntry.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ─── Memory Consolidation ──────────────────────────


async def consolidate_session_memory(
    db: AsyncSession,
    session_id: str,
    agent_id: UUID | None = None,
    max_entries: int = 50,
) -> int:
    """Summarize old memory entries when a session exceeds max_entries.
    
    Deletes entries beyond max_entries (keeping most recent).
    Returns count of consolidated (deleted) entries.
    """
    conditions = [MemoryEntry.session_id == session_id]
    if agent_id:
        conditions.append(MemoryEntry.agent_id == agent_id)

    # Count total
    count_result = await db.execute(select(func.count(MemoryEntry.id)).where(*conditions))
    total = count_result.scalar() or 0

    if total <= max_entries:
        return 0

    # Delete oldest entries beyond the limit
    delete_count = total - max_entries
    result = await db.execute(
        select(MemoryEntry.id)
        .where(*conditions)
        .order_by(MemoryEntry.created_at.asc())
        .limit(delete_count)
    )
    ids_to_delete = [row[0] for row in result.all()]

    if ids_to_delete:
        await db.execute(
            MemoryEntry.__table__.delete().where(MemoryEntry.id.in_(ids_to_delete))
        )
        await db.flush()

    return len(ids_to_delete)


async def update_importance(
    db: AsyncSession,
    entry_id: UUID,
    score: float,
) -> MemoryEntry | None:
    """Update the importance score of a memory entry."""
    entry = await get_entry(db, entry_id)
    if entry:
        entry.importance_score = score
        entry.access_count += 1
        await db.flush()
        await db.refresh(entry)
    return entry
