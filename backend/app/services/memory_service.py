"""Memory Engine service — CRUD, keyword search, session management (Firestore)."""

from app.core.db import FirestoreDB, now_iso, stamp
from app.schemas.memory import MemoryEntryCreate

MEMORY = "memory_entries"


# ─── Errors ──────────────────────────────────────────


class MemoryError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ─── CRUD ──────────────────────────────────────────


async def create_entry(
    db: FirestoreDB,
    entry_in: MemoryEntryCreate,
    workspace_id: str | None = None,
    agent_id: str | None = None,
) -> dict:
    """Store a new memory entry."""
    entry = stamp({
        "workspace_id": str(workspace_id) if workspace_id else None,
        "agent_id": str(agent_id) if agent_id else None,
        "session_id": entry_in.session_id,
        "role": entry_in.role,
        "content": entry_in.content,
        "memory_type": entry_in.memory_type,
        "entry_metadata": entry_in.metadata,
        "importance_score": None,
        "access_count": 0,
    })
    db.add(MEMORY, entry)
    return entry


async def get_entry(db: FirestoreDB, entry_id: str) -> dict | None:
    return db.get(MEMORY, str(entry_id))


async def list_session_memory(
    db: FirestoreDB,
    session_id: str,
    agent_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Get all memory entries for a conversation session."""
    rows = [r for r in db.query(MEMORY, "session_id", session_id) if not r.get("deleted_at")]
    if agent_id:
        rows = [r for r in rows if str(r.get("agent_id") or "") == str(agent_id)]
    rows.sort(key=lambda r: r.get("created_at") or "")
    return rows[:limit]


async def list_agent_memory(
    db: FirestoreDB,
    agent_id: str,
    memory_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """List all memory for an agent."""
    rows = [
        r for r in db.query(MEMORY, "agent_id", str(agent_id))
        if (memory_type is None or r.get("memory_type") == memory_type)
    ]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def list_workspace_memory(
    db: FirestoreDB,
    workspace_id: str,
    agent_id: str | None = None,
    memory_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List memory entries for a workspace."""
    rows = [
        r for r in db.query(MEMORY, "workspace_id", str(workspace_id))
        if (agent_id is None or str(r.get("agent_id") or "") == str(agent_id))
        and (memory_type is None or r.get("memory_type") == memory_type)
    ]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[:limit]


async def delete_entry(db: FirestoreDB, entry: dict) -> None:
    db.delete(MEMORY, entry["id"])


async def clear_session(db: FirestoreDB, session_id: str) -> int:
    """Clear all memory for a session. Returns count of deleted entries."""
    entries = [r for r in db.query(MEMORY, "session_id", session_id)]
    for entry in entries:
        db.delete(MEMORY, entry["id"])
    return len(entries)


# ─── Search ─────────────────────────────────────────


async def search_memory(
    db: FirestoreDB,
    query: str,
    workspace_id: str | None = None,
    agent_id: str | None = None,
    memory_type: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Simple keyword-based memory search (no vector embeddings yet)."""
    rows = [r for r in db.query(MEMORY) if not r.get("deleted_at")]

    search_terms = query.lower().split()
    if search_terms:
        rows = [
            r for r in rows
            if all(term in (r.get("content") or "").lower() for term in search_terms)
        ]
    if workspace_id:
        rows = [r for r in rows if str(r.get("workspace_id") or "") == str(workspace_id)]
    if agent_id:
        rows = [r for r in rows if str(r.get("agent_id") or "") == str(agent_id)]
    if memory_type:
        rows = [r for r in rows if r.get("memory_type") == memory_type]

    # importance desc (None treated as lowest), then created desc
    rows.sort(
        key=lambda r: (
            r.get("importance_score") is None,
            r.get("importance_score") or 0,
            r.get("created_at") or "",
        ),
        reverse=True,
    )
    return rows[:limit]


# ─── Memory Consolidation ──────────────────────────


async def consolidate_session_memory(
    db: FirestoreDB,
    session_id: str,
    agent_id: str | None = None,
    max_entries: int = 50,
) -> int:
    """Delete the oldest entries once a session exceeds max_entries."""
    rows = [r for r in db.query(MEMORY, "session_id", session_id)]
    if agent_id:
        rows = [r for r in rows if str(r.get("agent_id") or "") == str(agent_id)]

    if len(rows) <= max_entries:
        return 0

    rows.sort(key=lambda r: r.get("created_at") or "")
    to_delete = rows[: len(rows) - max_entries]
    for entry in to_delete:
        db.delete(MEMORY, entry["id"])
    return len(to_delete)


async def consolidate_workspace_memory(
    db: FirestoreDB,
    workspace_id: str,
    max_entries: int = 50,
) -> int:
    """Trim the oldest workspace memory entries once the workspace exceeds
    ``max_entries`` (global consolidation). Higher-importance entries are kept."""
    rows = [
        r for r in db.query(MEMORY, "workspace_id", str(workspace_id))
        if not r.get("deleted_at")
    ]
    if len(rows) <= max_entries:
        return 0

    # Delete the oldest, least-important overflow first: sort ascending by
    # (importance with None treated as lowest, then created_at), and drop the
    # head of the list. High-importance entries always survive trimming.
    rows.sort(key=lambda r: (
        r.get("importance_score") is not None,
        r.get("importance_score") or 0,
        r.get("created_at") or "",
    ))
    to_delete = rows[: len(rows) - max_entries]
    for entry in to_delete:
        db.delete(MEMORY, entry["id"])
    return len(to_delete)


async def update_importance(
    db: FirestoreDB,
    entry_id: str,
    score: float,
) -> dict | None:
    """Update the importance score of a memory entry."""
    entry = await get_entry(db, entry_id)
    if entry:
        entry["importance_score"] = score
        entry["access_count"] = (entry.get("access_count") or 0) + 1
        db.set(MEMORY, entry["id"], entry)
    return entry
