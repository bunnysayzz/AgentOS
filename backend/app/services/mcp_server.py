"""Real Model Context Protocol (MCP) server for AgentOS.

Exposes the platform to any MCP client (Claude Desktop, Cursor, Claude Code,
MCP Inspector…) over the **Streamable HTTP** transport (mounted at ``/mcp`` by
``app.main``) or **stdio** (``python -m app.services.mcp_server``).

Authentication for the HTTP transport is enforced by an ASGI middleware in
``app.main`` (Bearer API key, or ``MCP_ACCESS_TOKEN`` when configured). Tools
take an explicit ``workspace_id`` — list workspaces first to discover them.

Every tool is async and opens its own Firestore handle, so no request-scoped
state leaks between calls.
"""

from mcp.server.fastmcp import FastMCP

from app.core.db import FirestoreDB
from app.schemas.mcp import ChatCompletionRequest, ChatMessage
from app.schemas.memory import MemoryEntryCreate
from app.services import (
    agent_service,
    mcp_service,
    memory_service,
    tool_service,
    workspace_service,
)

mcp = FastMCP("agentos")


# ─── Workspaces ─────────────────────────────────────


@mcp.tool()
async def list_workspaces() -> list[dict]:
    """List all workspaces in the platform (id, name, slug, description)."""
    db = FirestoreDB()
    rows = db.query(workspace_service.WORKSPACES)
    out = []
    for w in rows:
        if not w.get("deleted_at"):
            out.append({
                "id": w.get("id"),
                "name": w.get("name"),
                "slug": w.get("slug"),
                "description": w.get("description"),
            })
    return out


# ─── Agents ─────────────────────────────────────────


@mcp.tool()
async def list_agents(workspace_id: str) -> list[dict]:
    """List agents in a workspace (id, name, model, status)."""
    db = FirestoreDB()
    agents, _ = await agent_service.list_workspace_agents(db, workspace_id)
    return [
        {
            "id": a.get("id"),
            "name": a.get("name"),
            "description": a.get("description"),
            "model_provider": a.get("model_provider"),
            "model_name": a.get("model_name"),
            "status": a.get("status"),
        }
        for a in agents
    ]


@mcp.tool()
async def run_agent(workspace_id: str, agent_name: str, input: str) -> dict:
    """Run an agent by name with the given input and wait for its output.

    Runs synchronously in-process (may take several seconds for tool loops).
    Returns the completed execution: status, response, tokens, cost.
    """
    db = FirestoreDB()
    agents, _ = await agent_service.list_workspace_agents(db, workspace_id)
    agent = next(
        (a for a in agents if (a.get("name") or "").lower() == agent_name.lower()),
        None,
    )
    if agent is None:
        return {"ok": False, "error": f"Agent '{agent_name}' not found in workspace"}

    from app.schemas.agent import AgentExecutionCreate
    from app.services.execution_engine import run_agent_execution

    execution = await agent_service.create_execution(
        db, agent["id"], AgentExecutionCreate(input_data={"input": input})
    )
    execution = await agent_service.start_execution(db, execution)
    await run_agent_execution(db, execution["id"])

    done = await agent_service.get_execution_by_id(db, execution["id"])
    return {
        "ok": done.get("status") == "completed",
        "status": done.get("status"),
        "response": (done.get("output_data") or {}).get("response"),
        "tool_steps": (done.get("output_data") or {}).get("tool_steps"),
        "error": done.get("error_message"),
        "prompt_tokens": done.get("prompt_tokens"),
        "completion_tokens": done.get("completion_tokens"),
        "cost_usd": done.get("cost_usd"),
    }


# ─── Tools ──────────────────────────────────────────


@mcp.tool()
async def list_tools(workspace_id: str | None = None) -> list[dict]:
    """List registered tools (optionally scoped to a workspace)."""
    db = FirestoreDB()
    if workspace_id:
        tools, _ = await tool_service.list_workspace_tools(db, workspace_id)
    else:
        tools, _ = await tool_service.list_public_tools(db)
    return [
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "slug": t.get("slug"),
            "description": t.get("description"),
            "tool_type": t.get("tool_type"),
        }
        for t in tools
    ]


@mcp.tool()
async def execute_tool(workspace_id: str, tool_name: str, params: dict) -> dict:
    """Execute a registered tool (HTTP endpoint) by name with the given params."""
    db = FirestoreDB()
    tools, _ = await tool_service.list_workspace_tools(db, workspace_id)
    tool = next(
        (t for t in tools if (t.get("name") or "").lower() == tool_name.lower()
         or (t.get("slug") or "") == tool_name),
        None,
    )
    if tool is None:
        return {"ok": False, "error": f"Tool '{tool_name}' not found in workspace"}

    from app.services.execution_engine import run_tool

    return await run_tool(db, tool, params=params or {})


# ─── Chat ───────────────────────────────────────────


@mcp.tool()
async def chat(message: str, model: str = "gpt-4o-mini", system_prompt: str | None = None) -> dict:
    """Send a chat message through the LLM gateway (provider fallback included)."""
    db = FirestoreDB()
    messages = []
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    messages.append(ChatMessage(role="user", content=message))

    response = await mcp_service.route_chat_completion(
        db,
        ChatCompletionRequest(model=model, messages=messages, temperature=0.7, max_tokens=2048),
    )
    content = response.choices[0]["message"]["content"] if response.choices else ""
    return {
        "response": content,
        "model": response.model,
        "provider": response.provider.value,
        "usage": response.usage,
        "cost_usd": response.cost_usd,
    }


# ─── Memory ─────────────────────────────────────────


@mcp.tool()
async def memory_search(workspace_id: str, query: str, limit: int = 10) -> list[dict]:
    """Search a workspace's memory by keyword."""
    db = FirestoreDB()
    return await memory_service.search_memory(
        db, query, workspace_id=workspace_id, limit=min(limit, 50)
    )


@mcp.tool()
async def memory_store(
    workspace_id: str,
    content: str,
    memory_type: str = "conversation",
    session_id: str | None = None,
) -> dict:
    """Store a memory entry in a workspace."""
    db = FirestoreDB()
    entry = await memory_service.create_entry(
        db,
        MemoryEntryCreate(role="user", content=content, memory_type=memory_type, session_id=session_id),
        workspace_id=workspace_id,
    )
    return {"id": entry["id"], "memory_type": memory_type}


# ─── stdio entry point (local dev / desktop clients) ──


if __name__ == "__main__":
    mcp.run()  # stdio transport
