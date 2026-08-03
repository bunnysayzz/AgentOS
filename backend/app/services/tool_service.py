"""Tool Registry service - tool CRUD, execution tracking (Firestore-backed)."""

from app.core.db import FirestoreDB, now_iso, stamp
from app.schemas.tool import ToolCreate, ToolUpdate

TOOLS = "tools"
TOOL_EXECUTIONS = "tool_executions"


# ─── Errors ──────────────────────────────────────────


class ToolError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ToolNotFoundError(ToolError):
    def __init__(self):
        super().__init__("Tool not found", status_code=404)


class ToolSlugTakenError(ToolError):
    def __init__(self):
        super().__init__("A tool with this slug already exists", status_code=409)


def _duration_ms(started_iso: str | None) -> int | None:
    if not started_iso:
        return None
    from datetime import datetime, timezone
    try:
        start = datetime.fromisoformat(started_iso.replace("Z", "+00:00"))
        return int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    except Exception:
        return None


# ─── Tool CRUD ──────────────────────────────────────


async def create_tool(
    db: FirestoreDB, tool_in: ToolCreate, workspace_id: str | None = None
) -> dict:
    """Create a new tool."""
    slug = tool_in.slug
    if slug is None:
        slug = tool_in.name.lower().replace(" ", "-").replace("_", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        if not slug:
            slug = "tool"

    for row in db.query(TOOLS, "slug", slug):
        if not row.get("deleted_at"):
            raise ToolSlugTakenError()

    tool = stamp({
        "workspace_id": str(workspace_id) if workspace_id else None,
        "name": tool_in.name,
        "slug": slug,
        "description": tool_in.description,
        "tool_type": tool_in.tool_type.value,
        "source": tool_in.source,
        "schema_definition": tool_in.schema_definition,
        "parameters": tool_in.parameters,
        "auth_type": tool_in.auth_type.value,
        "auth_config": tool_in.auth_config,
        "is_public": tool_in.is_public,
        "is_active": True,
        "version": 1,
        "tags": tool_in.tags,
    })
    db.add(TOOLS, tool)
    return tool


async def get_tool_by_id(db: FirestoreDB, tool_id: str) -> dict | None:
    """Get a tool by ID."""
    tool = db.get(TOOLS, str(tool_id))
    if tool is None or tool.get("deleted_at"):
        return None
    return tool


async def get_tool_by_slug(db: FirestoreDB, slug: str) -> dict | None:
    """Get a tool by slug."""
    for row in db.query(TOOLS, "slug", slug):
        if not row.get("deleted_at"):
            return row
    return None


async def list_workspace_tools(
    db: FirestoreDB, workspace_id: str, page: int = 1, page_size: int = 50
) -> tuple[list[dict], int]:
    """List tools available to a workspace (workspace tools + public tools)."""
    rows = [
        r for r in db.query(TOOLS)
        if r.get("is_active") and not r.get("deleted_at")
        and (str(r.get("workspace_id") or "") == str(workspace_id) or r.get("is_public"))
    ]
    rows.sort(key=lambda r: (r.get("tool_type") or "", r.get("name") or ""))
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def list_public_tools(
    db: FirestoreDB, page: int = 1, page_size: int = 50
) -> tuple[list[dict], int]:
    """List all public/builtin tools."""
    rows = [
        r for r in db.query(TOOLS)
        if r.get("is_public") and r.get("is_active") and not r.get("deleted_at")
    ]
    rows.sort(key=lambda r: r.get("name") or "")
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def update_tool(db: FirestoreDB, tool: dict, tool_in: ToolUpdate) -> dict:
    """Update a tool."""
    update_data = tool_in.model_dump(exclude_unset=True)

    config_fields = {"schema_definition", "parameters", "auth_config"}
    if config_fields & set(update_data.keys()):
        tool["version"] = (tool.get("version") or 1) + 1

    for field, value in update_data.items():
        if field == "auth_type" and value is not None:
            value = value.value if hasattr(value, "value") else value
        tool[field] = value

    db.set(TOOLS, tool["id"], tool)
    return tool


async def delete_tool(db: FirestoreDB, tool: dict) -> None:
    """Soft-delete a tool."""
    tool["deleted_at"] = now_iso()
    tool["is_active"] = False
    db.set(TOOLS, tool["id"], tool)


# ─── Tool Execution ─────────────────────────────────


async def create_tool_execution(
    db: FirestoreDB,
    tool_id: str,
    input_params: dict | None = None,
    execution_id: str | None = None,
) -> dict:
    """Create a new tool execution record."""
    tool_exec = stamp({
        "tool_id": str(tool_id),
        "execution_id": str(execution_id) if execution_id else None,
        "status": "pending",
        "input_params": input_params,
        "output_data": None,
        "error_message": None,
        "duration_ms": None,
        "started_at": None,
        "completed_at": None,
    })
    db.add(TOOL_EXECUTIONS, tool_exec)
    return tool_exec


async def complete_tool_execution(
    db: FirestoreDB,
    tool_exec: dict,
    output_data: dict | None = None,
) -> dict:
    """Mark a tool execution as successful."""
    tool_exec["status"] = "success"
    tool_exec["output_data"] = output_data
    tool_exec["completed_at"] = now_iso()
    if tool_exec.get("started_at"):
        tool_exec["duration_ms"] = _duration_ms(tool_exec["started_at"])
    else:
        tool_exec["started_at"] = tool_exec["completed_at"]
        tool_exec["duration_ms"] = 0
    db.set(TOOL_EXECUTIONS, tool_exec["id"], tool_exec)
    return tool_exec


async def fail_tool_execution(
    db: FirestoreDB,
    tool_exec: dict,
    error_message: str,
) -> dict:
    """Mark a tool execution as failed."""
    tool_exec["status"] = "failed"
    tool_exec["error_message"] = error_message
    tool_exec["completed_at"] = now_iso()
    if tool_exec.get("started_at"):
        tool_exec["duration_ms"] = _duration_ms(tool_exec["started_at"])
    db.set(TOOL_EXECUTIONS, tool_exec["id"], tool_exec)
    return tool_exec


async def list_tool_executions(
    db: FirestoreDB, tool_id: str, page: int = 1, page_size: int = 50
) -> tuple[list[dict], int]:
    """List executions for a tool."""
    rows = db.query(TOOL_EXECUTIONS, "tool_id", str(tool_id))
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total
