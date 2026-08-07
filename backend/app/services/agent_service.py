"""Agent service - CRUD, execution lifecycle, state machine (Firestore-backed)."""

import uuid
from datetime import datetime, timezone

from app.core.db import FirestoreDB, now_iso, stamp
from app.models.agent import AgentStatus, ExecutionStatus
from app.schemas.agent import AgentCreate, AgentUpdate, AgentExecutionCreate
from app.services import auth_service, workspace_service

AGENTS = "agents"
EXECUTIONS = "agent_executions"


# ─── Errors ──────────────────────────────────────────


class AgentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AgentNotFoundError(AgentError):
    def __init__(self):
        super().__init__("Agent not found", status_code=404)


class InvalidTransitionError(AgentError):
    def __init__(self, current: ExecutionStatus, target: ExecutionStatus):
        super().__init__(
            f"Cannot transition from {current.value} to {target.value}",
            status_code=400,
        )


# ─── State Machine ──────────────────────────────────

EXECUTION_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.PENDING: {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED},
    ExecutionStatus.RUNNING: {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.PAUSED, ExecutionStatus.CANCELLED},
    ExecutionStatus.PAUSED: {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED},
    ExecutionStatus.COMPLETED: set(),
    ExecutionStatus.FAILED: set(),
    ExecutionStatus.CANCELLED: set(),
}


def validate_transition(current: ExecutionStatus, target: ExecutionStatus) -> None:
    """Validate an execution status transition."""
    if target not in EXECUTION_TRANSITIONS.get(current, set()):
        raise InvalidTransitionError(current, target)


def _duration_ms(started_iso: str | None) -> int | None:
    if not started_iso:
        return None
    try:
        start = datetime.fromisoformat(started_iso.replace("Z", "+00:00"))
        return int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    except Exception:
        return None


# ─── Agent CRUD ─────────────────────────────────────


async def create_agent(db: FirestoreDB, workspace_id: str, agent_in: AgentCreate) -> dict:
    """Create a new agent within a workspace."""
    agent = stamp({
        "workspace_id": str(workspace_id),
        "name": agent_in.name,
        "description": agent_in.description,
        "system_prompt": agent_in.system_prompt,
        "model_provider": agent_in.model_provider,
        "model_name": agent_in.model_name,
        "temperature": agent_in.temperature,
        "max_tokens": agent_in.max_tokens,
        "config": agent_in.config,
        "tool_ids": agent_in.tool_ids,
        "status": AgentStatus.DRAFT.value,
        "version": 1,
        # Gallery fields — nothing starts published.
        "published": False,
        "published_at": None,
        "cloned_from": None,
    })
    db.add(AGENTS, agent)
    return agent


async def get_agent_by_id(db: FirestoreDB, agent_id: str) -> dict | None:
    """Get an agent by ID."""
    agent = db.get(AGENTS, str(agent_id))
    if agent is None or agent.get("deleted_at"):
        return None
    return agent


async def list_workspace_agents(
    db: FirestoreDB, workspace_id: str, page: int = 1, page_size: int = 50
) -> tuple[list[dict], int]:
    """List all agents in a workspace with pagination."""
    rows = [r for r in db.query(AGENTS, "workspace_id", str(workspace_id)) if not r.get("deleted_at")]
    rows.sort(key=lambda r: (r.get("updated_at") or "", r.get("created_at") or ""), reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def update_agent(db: FirestoreDB, agent: dict, agent_in: AgentUpdate) -> dict:
    """Update an agent."""
    update_data = agent_in.model_dump(exclude_unset=True)

    config_fields = {"system_prompt", "model_provider", "model_name", "temperature", "max_tokens", "config", "tool_ids"}
    if config_fields & set(update_data.keys()):
        agent["version"] = (agent.get("version") or 1) + 1

    for field, value in update_data.items():
        if value is not None or field == "config" or field == "tool_ids":
            agent[field] = value
        else:
            agent[field] = value

    db.set(AGENTS, agent["id"], agent)
    return agent


async def delete_agent(db: FirestoreDB, agent: dict) -> None:
    """Soft-delete an agent."""
    agent["deleted_at"] = now_iso()
    agent["status"] = AgentStatus.ARCHIVED.value
    agent["published"] = False
    agent["published_at"] = None
    db.set(AGENTS, agent["id"], agent)


# ─── Gallery (publish / unpublish / clone) ─────────────


async def set_published(db: FirestoreDB, agent: dict, published: bool) -> dict:
    """Publish or unpublish an agent in the public community gallery.

    Only ACTIVE agents can be published — a draft/paused agent has no place
    in a public gallery.
    """
    if published and agent.get("status") != AgentStatus.ACTIVE.value:
        raise AgentError(
            "Only active agents can be published. Activate the agent first.",
            status_code=400,
        )
    agent["published"] = published
    agent["published_at"] = now_iso() if published else None
    db.set(AGENTS, agent["id"], agent)
    return agent


def _enrich_gallery_agent(db: FirestoreDB, agent: dict) -> dict:
    """Attach public metadata (author username, workspace name) to an agent."""
    ws = None
    if agent.get("workspace_id"):
        ws = db.get(workspace_service.WORKSPACES, str(agent["workspace_id"]))
    owner = None
    if ws and ws.get("owner_id"):
        owner = auth_service.get_user_by_id(db, ws["owner_id"]) or {}
    enriched = dict(agent)
    enriched["author_username"] = (owner or {}).get("username") or "anonymous"
    enriched["workspace_name"] = (ws or {}).get("name") or "Unknown workspace"
    enriched["tool_count"] = len(agent.get("tool_ids") or [])
    return enriched


async def list_published_agents(
    db: FirestoreDB, page: int = 1, page_size: int = 24
) -> tuple[list[dict], int]:
    """List all published agents (newest first) with author info.

    The single equality filter (published == True) is pushed to Firestore;
    soft-deletes are filtered out in Python.
    """
    rows = [r for r in db.query(AGENTS, "published", True) if not r.get("deleted_at")]
    rows.sort(key=lambda r: r.get("published_at") or "", reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return [_enrich_gallery_agent(db, r) for r in rows[start : start + page_size]], total


async def get_published_agent_by_id(db: FirestoreDB, agent_id: str) -> dict | None:
    """Get a single published agent (public gallery view)."""
    agent = await get_agent_by_id(db, agent_id)
    if agent is None or not agent.get("published"):
        return None
    return _enrich_gallery_agent(db, agent)


async def clone_agent(db: FirestoreDB, source: dict, target_workspace_id: str) -> dict:
    """Clone a published agent into another workspace.

    Safety: secrets are workspace-scoped and encrypted, and tool bindings are
    workspace-scoped — neither is copied. The clone starts as a DRAFT so the
    user reviews and activates it before it can run.
    """
    config = dict(source.get("config") or {})
    config.pop("injected_secrets", None)

    source_desc = (source.get("description") or "").strip()
    description = source_desc + (
        "\n\nCloned from the AgentOS community gallery." if source_desc
        else "Cloned from the AgentOS community gallery."
    )

    agent = stamp({
        "workspace_id": str(target_workspace_id),
        "name": source.get("name", "Untitled agent"),
        "description": description,
        "system_prompt": source.get("system_prompt"),
        "model_provider": source.get("model_provider", "openai"),
        "model_name": source.get("model_name", "gpt-4o"),
        "temperature": source.get("temperature", 0.7),
        "max_tokens": source.get("max_tokens", 4096),
        "config": config,
        "tool_ids": [],
        "status": AgentStatus.DRAFT.value,
        "version": 1,
        "published": False,
        "published_at": None,
        "cloned_from": source.get("id"),
    })
    db.add(AGENTS, agent)
    return agent


# ─── Execution Lifecycle ────────────────────────────


async def create_execution(
    db: FirestoreDB, agent_id: str, exec_in: AgentExecutionCreate | None = None
) -> dict:
    """Create a new execution for an agent."""
    agent = await get_agent_by_id(db, agent_id)
    if agent is None:
        raise AgentNotFoundError()

    session_id = exec_in.session_id if exec_in and exec_in.session_id else str(uuid.uuid4())

    execution = stamp({
        "agent_id": str(agent_id),
        "session_id": session_id,
        "status": ExecutionStatus.PENDING.value,
        "input_data": exec_in.input_data if exec_in else None,
        "output_data": None,
        "error_message": None,
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
        "checkpoint_path": None,
    })
    db.add(EXECUTIONS, execution)
    return execution


async def get_execution_by_id(db: FirestoreDB, execution_id: str) -> dict | None:
    """Get an execution by ID."""
    return db.get(EXECUTIONS, str(execution_id))


async def list_agent_executions(
    db: FirestoreDB,
    agent_id: str,
    page: int = 1,
    page_size: int = 50,
    status_filter: ExecutionStatus | None = None,
) -> tuple[list[dict], int]:
    """List executions for an agent."""
    rows = [
        r for r in db.query(EXECUTIONS, "agent_id", str(agent_id))
        if (status_filter is None or r.get("status") == status_filter.value)
    ]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def start_execution(db: FirestoreDB, execution: dict) -> dict:
    """Start an execution (PENDING -> RUNNING)."""
    validate_transition(ExecutionStatus(execution["status"]), ExecutionStatus.RUNNING)
    execution["status"] = ExecutionStatus.RUNNING.value
    execution["started_at"] = now_iso()
    db.set(EXECUTIONS, execution["id"], execution)
    return execution


async def complete_execution(
    db: FirestoreDB,
    execution: dict,
    output_data: dict | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    cost_usd: float | None = None,
) -> dict:
    """Complete an execution (RUNNING -> COMPLETED)."""
    validate_transition(ExecutionStatus(execution["status"]), ExecutionStatus.COMPLETED)

    execution["status"] = ExecutionStatus.COMPLETED.value
    execution["completed_at"] = now_iso()
    execution["output_data"] = output_data
    execution["prompt_tokens"] = prompt_tokens
    execution["completion_tokens"] = completion_tokens
    if prompt_tokens is not None and completion_tokens is not None:
        execution["total_tokens"] = prompt_tokens + completion_tokens
    execution["cost_usd"] = cost_usd
    execution["duration_ms"] = _duration_ms(execution.get("started_at"))

    db.set(EXECUTIONS, execution["id"], execution)
    return execution


async def fail_execution(db: FirestoreDB, execution: dict, error_message: str) -> dict:
    """Fail an execution (RUNNING -> FAILED)."""
    validate_transition(ExecutionStatus(execution["status"]), ExecutionStatus.FAILED)

    execution["status"] = ExecutionStatus.FAILED.value
    execution["completed_at"] = now_iso()
    execution["error_message"] = error_message
    execution["duration_ms"] = _duration_ms(execution.get("started_at"))

    db.set(EXECUTIONS, execution["id"], execution)
    return execution


async def cancel_execution(db: FirestoreDB, execution: dict) -> dict:
    """Cancel an execution (any active state -> CANCELLED)."""
    validate_transition(ExecutionStatus(execution["status"]), ExecutionStatus.CANCELLED)

    execution["status"] = ExecutionStatus.CANCELLED.value
    execution["completed_at"] = now_iso()
    execution["duration_ms"] = _duration_ms(execution.get("started_at"))

    db.set(EXECUTIONS, execution["id"], execution)
    return execution


async def pause_execution(db: FirestoreDB, execution: dict) -> dict:
    """Pause an execution (RUNNING -> PAUSED)."""
    validate_transition(ExecutionStatus(execution["status"]), ExecutionStatus.PAUSED)
    execution["status"] = ExecutionStatus.PAUSED.value
    db.set(EXECUTIONS, execution["id"], execution)
    return execution


async def resume_execution(db: FirestoreDB, execution: dict) -> dict:
    """Resume a paused execution (PAUSED -> RUNNING)."""
    validate_transition(ExecutionStatus(execution["status"]), ExecutionStatus.RUNNING)
    execution["status"] = ExecutionStatus.RUNNING.value
    db.set(EXECUTIONS, execution["id"], execution)
    return execution


# ─── Session Management ─────────────────────────────


async def list_session_executions(
    db: FirestoreDB, session_id: str, workspace_id: str | None = None, agent_id: str | None = None
) -> list[dict]:
    """List all executions in a session, optionally scoped to a workspace."""
    rows = [r for r in db.query(EXECUTIONS, "session_id", session_id)]

    if workspace_id:
        agent_ids = {
            a["id"] for a in db.query(AGENTS, "workspace_id", str(workspace_id))
        }
        rows = [r for r in rows if r.get("agent_id") in agent_ids]

    if agent_id:
        rows = [r for r in rows if str(r.get("agent_id") or "") == str(agent_id)]

    rows.sort(key=lambda r: r.get("created_at") or "")
    return rows
