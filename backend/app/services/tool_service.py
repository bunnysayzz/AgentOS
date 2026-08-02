"""Tool Registry service - tool CRUD, execution tracking, public tool discovery."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool import Tool, ToolExecution, ToolType, ToolAuthType
from app.schemas.tool import ToolCreate, ToolUpdate
from app.core.timeutils import safe_duration_ms


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


# ─── Tool CRUD ──────────────────────────────────────


async def create_tool(
    db: AsyncSession, tool_in: ToolCreate, workspace_id: UUID | None = None
) -> Tool:
    """Create a new tool."""
    # Auto-generate slug from name if not provided
    slug = tool_in.slug
    if slug is None:
        slug = tool_in.name.lower().replace(" ", "-").replace("_", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        if not slug:
            slug = "tool"

    # Check slug uniqueness
    result = await db.execute(select(Tool).where(Tool.slug == slug))
    if result.scalar_one_or_none():
        raise ToolSlugTakenError()

    tool = Tool(
        workspace_id=workspace_id,
        name=tool_in.name,
        slug=slug,
        description=tool_in.description,
        tool_type=tool_in.tool_type,
        source=tool_in.source,
        schema_definition=tool_in.schema_definition,
        parameters=tool_in.parameters,
        auth_type=tool_in.auth_type,
        auth_config=tool_in.auth_config,
        is_public=tool_in.is_public,
        tags=tool_in.tags,
    )
    db.add(tool)
    await db.flush()
    await db.refresh(tool)
    return tool


async def get_tool_by_id(db: AsyncSession, tool_id: UUID) -> Tool | None:
    """Get a tool by ID."""
    result = await db.execute(select(Tool).where(Tool.id == tool_id, Tool.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def get_tool_by_slug(db: AsyncSession, slug: str) -> Tool | None:
    """Get a tool by slug."""
    result = await db.execute(select(Tool).where(Tool.slug == slug, Tool.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def list_workspace_tools(
    db: AsyncSession, workspace_id: UUID, page: int = 1, page_size: int = 50
) -> tuple[list[Tool], int]:
    """List tools available to a workspace (workspace tools + public tools)."""
    offset = (page - 1) * page_size

    # Workspace tools + public tools from other workspaces
    base_conditions = [
        Tool.is_active.is_(True),
        Tool.deleted_at.is_(None),
        or_(
            Tool.workspace_id == workspace_id,
            Tool.is_public.is_(True),
        ),
    ]

    count_result = await db.execute(
        select(func.count(Tool.id)).where(*base_conditions)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Tool)
        .where(*base_conditions)
        .order_by(Tool.tool_type, Tool.name.asc())
        .offset(offset)
        .limit(page_size)
    )
    tools = result.scalars().all()
    return list(tools), total


async def list_public_tools(
    db: AsyncSession, page: int = 1, page_size: int = 50
) -> tuple[list[Tool], int]:
    """List all public/builtin tools."""
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(Tool.id)).where(
            Tool.is_public.is_(True),
            Tool.is_active.is_(True),
            Tool.deleted_at.is_(None),
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Tool)
        .where(
            Tool.is_public.is_(True),
            Tool.is_active.is_(True),
            Tool.deleted_at.is_(None),
        )
        .order_by(Tool.name.asc())
        .offset(offset)
        .limit(page_size)
    )
    tools = result.scalars().all()
    return list(tools), total


async def update_tool(db: AsyncSession, tool: Tool, tool_in: ToolUpdate) -> Tool:
    """Update a tool."""
    update_data = tool_in.model_dump(exclude_unset=True)

    # Increment version on schema/config changes
    config_fields = {"schema_definition", "parameters", "auth_config"}
    if config_fields & set(update_data.keys()):
        tool.version += 1

    for field, value in update_data.items():
        setattr(tool, field, value)

    await db.flush()
    await db.refresh(tool)
    return tool


async def delete_tool(db: AsyncSession, tool: Tool) -> None:
    """Soft-delete a tool."""
    tool.deleted_at = datetime.now(timezone.utc)
    tool.is_active = False
    await db.flush()


# ─── Tool Execution ─────────────────────────────────


async def create_tool_execution(
    db: AsyncSession,
    tool_id: UUID,
    input_params: dict | None = None,
    execution_id: UUID | None = None,
) -> ToolExecution:
    """Create a new tool execution record."""
    tool_exec = ToolExecution(
        tool_id=tool_id,
        execution_id=execution_id,
        status="pending",
        input_params=input_params,
    )
    db.add(tool_exec)
    await db.flush()
    await db.refresh(tool_exec)
    return tool_exec


async def complete_tool_execution(
    db: AsyncSession,
    tool_exec: ToolExecution,
    output_data: dict | None = None,
) -> ToolExecution:
    """Mark a tool execution as successful."""
    now = datetime.now(timezone.utc)
    tool_exec.status = "success"
    tool_exec.output_data = output_data
    tool_exec.completed_at = now
    if tool_exec.started_at:
        tool_exec.duration_ms = safe_duration_ms(tool_exec.started_at)
    else:
        tool_exec.started_at = now
        tool_exec.duration_ms = 0
    await db.flush()
    await db.refresh(tool_exec)
    return tool_exec


async def fail_tool_execution(
    db: AsyncSession,
    tool_exec: ToolExecution,
    error_message: str,
) -> ToolExecution:
    """Mark a tool execution as failed."""
    now = datetime.now(timezone.utc)
    tool_exec.status = "failed"
    tool_exec.error_message = error_message
    tool_exec.completed_at = now
    if tool_exec.started_at:
        tool_exec.duration_ms = safe_duration_ms(tool_exec.started_at)
    await db.flush()
    await db.refresh(tool_exec)
    return tool_exec


async def list_tool_executions(
    db: AsyncSession, tool_id: UUID, page: int = 1, page_size: int = 50
) -> tuple[list[ToolExecution], int]:
    """List executions for a tool."""
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(ToolExecution.id)).where(ToolExecution.tool_id == tool_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ToolExecution)
        .where(ToolExecution.tool_id == tool_id)
        .order_by(ToolExecution.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    executions = result.scalars().all()
    return list(executions), total
