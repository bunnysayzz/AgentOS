"""Execution Engine — actually runs agents, tools, and workflow DAGs.

This is the runtime that turns execution *records* into real work:

- ``run_agent_execution`` loads the agent, calls the LLM through the MCP
  gateway (honoring the agent's configured provider + model), records an
  execution-graph node with tokens/cost, and completes/fails the execution.
- ``run_tool`` invokes a tool's HTTP endpoint with resolved params and auth.
- ``run_workflow_execution`` walks a workflow's DAG in topological order,
  executing agent/tool nodes, recording a graph node per node, pausing at
  approval gates, and completing/failing the overall execution.

Executions are kicked off in-process via ``asyncio.create_task`` (single
service, no broker required). Every function is idempotent-guarded and
never raises out of the background task.
"""

import asyncio
import json
import time
from datetime import datetime, timezone

import httpx

from app.core.db import FirestoreDB
from app.models.agent import ExecutionStatus
from app.models.execution_graph import NodeStatus, NodeType
from app.models.workflow import WorkflowExecutionStatus
from app.schemas.mcp import ChatCompletionRequest, ChatMessage
from app.services import (
    agent_service,
    execution_graph_service,
    mcp_service,
    tool_service,
    workflow_service,
)

# Default HTTP timeout for a single tool call (overridable per tool config).
TOOL_TIMEOUT_SECONDS = 60


# ─── Scheduling ───────────────────────────────────────


def schedule(db: FirestoreDB, coro_factory) -> asyncio.Task:
    """Create an in-process background task, swallowing startup issues."""

    async def _runner():
        try:
            await coro_factory()
        except Exception:
            # Never let a background task take the process down.
            import traceback
            traceback.print_exc()

    try:
        return asyncio.get_running_loop().create_task(_runner())
    except RuntimeError:
        # No running loop (e.g. during tests/import) — run inline instead.
        try:
            asyncio.run(_runner())
        except Exception:
            pass
        return None


# ─── Agent execution ──────────────────────────────────


def _user_text_from_input(input_data: dict | None) -> str:
    """Extract a user message from an agent execution's input_data."""
    data = input_data or {}
    for key in ("input", "message", "task", "prompt"):
        if data.get(key):
            return str(data[key])
    if data:
        return json.dumps(data, default=str)
    return "Run the agent."


def _is_all_providers_error(content: str) -> bool:
    """Detect the MCP gateway's 'all providers unavailable' sentinel."""
    return bool(content) and content.startswith("⚠️ All providers unavailable")


async def run_agent_execution(db: FirestoreDB, execution_id: str) -> None:
    """Execute a single agent: call the LLM, record graph node, finish."""
    execution = await agent_service.get_execution_by_id(db, execution_id)
    if execution is None or execution.get("status") != ExecutionStatus.RUNNING.value:
        return

    agent = await agent_service.get_agent_by_id(db, execution["agent_id"])
    if agent is None:
        await agent_service.fail_execution(db, execution, "Agent not found")
        return

    node = await execution_graph_service.create_node(
        db,
        execution_id,
        NodeType.AGENT_CALL,
        node_name=agent.get("name"),
        model_provider=agent.get("model_provider"),
        model_name=agent.get("model_name"),
    )
    await execution_graph_service.update_node_status(db, node, NodeStatus.RUNNING)
    started = time.monotonic()

    messages: list[ChatMessage] = []
    if agent.get("system_prompt"):
        messages.append(ChatMessage(role="system", content=agent["system_prompt"]))
    messages.append(ChatMessage(role="user", content=_user_text_from_input(execution.get("input_data"))))

    try:
        from app.models.mcp import LLMProvider

        preferred = None
        try:
            preferred = LLMProvider(agent.get("model_provider") or "openai")
        except ValueError:
            preferred = None

        response = await mcp_service.route_chat_completion(
            db,
            ChatCompletionRequest(
                model=agent.get("model_name") or "gpt-4o",
                messages=messages,
                temperature=agent.get("temperature"),
                max_tokens=agent.get("max_tokens"),
            ),
            workspace_id=agent.get("workspace_id"),
            agent_id=agent["id"],
            execution_id=execution_id,
            preferred_provider=preferred,
        )

        content = response.choices[0]["message"]["content"] if response.choices else ""
        prompt_tokens = response.usage.get("prompt_tokens", 0)
        completion_tokens = response.usage.get("completion_tokens", 0)

        # The gateway returns a simulated error payload (not an exception) when
        # no provider has a usable key. Treat that as a failure, not success.
        if _is_all_providers_error(content):
            raise RuntimeError(content[:200])

        await agent_service.complete_execution(
            db,
            execution,
            output_data={
                "response": content,
                "provider": response.provider.value,
                "model": response.model,
            },
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=response.cost_usd,
        )
        await execution_graph_service.update_node_status(
            db,
            node,
            NodeStatus.COMPLETED,
            output_data={"response": content},
            duration_ms=int((time.monotonic() - started) * 1000),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=response.cost_usd,
        )
    except Exception as exc:
        error = str(exc)
        await agent_service.fail_execution(db, execution, error)
        await execution_graph_service.update_node_status(
            db,
            node,
            NodeStatus.FAILED,
            error_message=error,
            duration_ms=int((time.monotonic() - started) * 1000),
        )


# ─── Tool execution ───────────────────────────────────


def _build_tool_url(tool: dict, params: dict) -> str:
    """Build the full tool URL from source + url_template with {param} fills."""
    source = (tool.get("source") or "").strip()
    parameters = tool.get("parameters") or {}
    url_template = parameters.get("url_template") or ""

    try:
        if url_template:
            filled = url_template.format(**params)
            base = source.rstrip("/") if source else ""
            return f"{base}{filled}" if base else filled
        return source.format(**params)
    except (KeyError, IndexError):
        return source or ""


def _build_tool_headers(tool: dict) -> dict:
    """Resolve auth headers from the tool's auth config."""
    auth_type = (tool.get("auth_type") or "none").lower()
    auth_config = tool.get("auth_config") or {}
    headers = {"Content-Type": "application/json"}

    if auth_type in ("bearer", "api_key"):
        token = auth_config.get("api_key") or auth_config.get("token") or auth_config.get("value")
        if token:
            header_name = auth_config.get("header", "Authorization")
            if header_name.lower() == "authorization":
                scheme = auth_config.get("scheme", "Bearer")
                headers[header_name] = f"{scheme} {token}"
            else:
                headers[header_name] = token
    return headers


async def run_tool(
    db: FirestoreDB,
    tool: dict,
    params: dict | None = None,
    execution_id: str | None = None,
) -> dict:
    """Invoke a tool's HTTP endpoint and record the tool execution."""
    params = params or {}
    tool_exec = await tool_service.create_tool_execution(
        db, tool["id"], input_params=params, execution_id=execution_id
    )
    tool_exec["started_at"] = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()

    try:
        url = _build_tool_url(tool, params)
        if not url:
            raise ValueError(f"Tool '{tool.get('name')}' has no resolvable source URL")

        method = ((tool.get("parameters") or {}).get("method") or "GET").upper()
        headers = _build_tool_headers(tool)
        timeout = min(
            (tool.get("parameters") or {}).get("timeout_seconds") or TOOL_TIMEOUT_SECONDS,
            TOOL_TIMEOUT_SECONDS,
        )

        body = None
        query_params = None
        if method in ("POST", "PUT", "PATCH"):
            body = params
            # Strip path placeholders that don't belong in the JSON body.
            body = {k: v for k, v in body.items() if "{" not in str(k)}
        else:
            # GET/DELETE/HEAD: send unconsumed params as a query string.
            query_params = {k: v for k, v in params.items() if "{" not in str(k)} or None

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url, json=body or None, headers=headers, params=query_params)

        output: dict = {
            "status_code": response.status_code,
            "ok": response.status_code < 400,
        }
        try:
            output["data"] = response.json()
        except Exception:
            output["data"] = response.text[:2000]

        if response.status_code >= 400:
            raise ValueError(f"HTTP {response.status_code}: {output.get('data')}")

        tool_exec = await tool_service.complete_tool_execution(db, tool_exec, output_data=output)
        return output

    except Exception as exc:
        error = str(exc)
        tool_exec = await tool_service.fail_tool_execution(db, tool_exec, error)
        return {"ok": False, "error": error}


# ─── Workflow DAG execution ───────────────────────────


def _topological_order(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Return nodes in a valid execution order (Kahn's algorithm)."""
    node_ids = [n.get("id") for n in nodes if n.get("id")]
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    indegree: dict[str, int] = {nid: 0 for nid in node_ids}

    for edge in edges:
        src, tgt = edge.get("source"), edge.get("target")
        if src in adj and tgt in adj:
            adj[src].append(tgt)
            indegree[tgt] += 1

    queue = [nid for nid in node_ids if indegree[nid] == 0]
    order: list[dict] = []
    by_id = {n.get("id"): n for n in nodes}

    while queue:
        queue.sort()
        nid = queue.pop(0)
        if nid in by_id:
            order.append(by_id[nid])
        for neighbor in adj.get(nid, []):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    # Fall back to definition order if the graph is cyclic/partial.
    if len(order) < len(node_ids):
        return [n for n in nodes if n not in order]
    return order


def _node_input(node: dict, context: dict) -> dict:
    """Resolve a node's input params from its config and upstream context."""
    config = node.get("config") or {}
    raw = config.get("input") or config.get("params") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {"value": raw}
    result: dict = {}
    for key, value in (raw or {}).items():
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            ref = value[2:-2].strip()
            # {{ node_id.output }} or {{ node_id }}
            parts = ref.split(".")
            upstream = context.get(parts[0])
            if isinstance(upstream, dict):
                result[key] = upstream.get(parts[1]) if len(parts) > 1 else upstream
            else:
                result[key] = upstream
        else:
            result[key] = value
    return result


async def _resolve_agent_by_name(db: FirestoreDB, workspace_id: str, name: str) -> dict | None:
    agents, _ = await agent_service.list_workspace_agents(db, workspace_id)
    return next((a for a in agents if (a.get("name") or "").lower() == (name or "").lower()), None)


async def _resolve_tool_by_name(db: FirestoreDB, workspace_id: str, name: str) -> dict | None:
    tools, _ = await tool_service.list_workspace_tools(db, workspace_id)
    return next((t for t in tools if (t.get("name") or "").lower() == (name or "").lower()), None)


async def _execute_workflow_node(
    db: FirestoreDB,
    workflow: dict,
    execution: dict,
    node: dict,
    context: dict,
    graph_nodes: dict,
) -> dict:
    """Execute a single DAG node; returns its output dict."""
    ntype = (node.get("type") or "").lower()
    nname = node.get("name") or node.get("id")
    ws_id = workflow["workspace_id"]
    node_input = _node_input(node, context)

    if ntype in ("agent", "agent_call"):
        agent = await _resolve_agent_by_name(db, ws_id, nname)
        if agent is None:
            raise ValueError(f"Agent '{nname}' not found in workspace")
        return await _run_workflow_agent(db, workflow, execution, node, agent, node_input, graph_nodes)

    if ntype in ("tool", "tool_call", "webhook"):
        tool = await _resolve_tool_by_name(db, ws_id, nname)
        if tool is None:
            raise ValueError(f"Tool '{nname}' not found in workspace")
        return await _run_workflow_tool(db, workflow, execution, node, tool, node_input, graph_nodes)

    if ntype in ("approval_gate", "approval", "human_input"):
        return {"status": "awaiting_approval"}

    # Unknown/pass-through node types: mark skipped and pass input through.
    gnode = await execution_graph_service.create_node(
        db, execution["id"], NodeType.FUNCTION, node_name=nname
    )
    await execution_graph_service.update_node_status(
        db, gnode, NodeStatus.SKIPPED, output_data={"type": ntype or "unknown"}
    )
    graph_nodes[node.get("id")] = gnode
    return {"type": ntype or "unknown", "input": node_input}


async def _run_workflow_agent(
    db: FirestoreDB,
    workflow: dict,
    execution: dict,
    node: dict,
    agent: dict,
    node_input: dict,
    graph_nodes: dict,
) -> dict:
    gnode = await execution_graph_service.create_node(
        db,
        execution["id"],
        NodeType.AGENT_CALL,
        node_name=agent.get("name"),
        model_provider=agent.get("model_provider"),
        model_name=agent.get("model_name"),
    )
    graph_nodes[node.get("id")] = gnode
    await execution_graph_service.update_node_status(db, gnode, NodeStatus.RUNNING)
    started = time.monotonic()

    messages: list[ChatMessage] = []
    if agent.get("system_prompt"):
        messages.append(ChatMessage(role="system", content=agent["system_prompt"]))
    messages.append(ChatMessage(role="user", content=_user_text_from_input(node_input)))

    from app.models.mcp import LLMProvider

    preferred = None
    try:
        preferred = LLMProvider(agent.get("model_provider") or "openai")
    except ValueError:
        preferred = None

    response = await mcp_service.route_chat_completion(
        db,
        ChatCompletionRequest(
            model=agent.get("model_name") or "gpt-4o",
            messages=messages,
            temperature=agent.get("temperature"),
            max_tokens=agent.get("max_tokens"),
        ),
        workspace_id=workflow.get("workspace_id"),
        agent_id=agent["id"],
        execution_id=execution["id"],
        preferred_provider=preferred,
    )
    content = response.choices[0]["message"]["content"] if response.choices else ""
    if _is_all_providers_error(content):
        raise RuntimeError(content[:200])
    await execution_graph_service.update_node_status(
        db,
        gnode,
        NodeStatus.COMPLETED,
        output_data={"response": content, "provider": response.provider.value, "model": response.model},
        duration_ms=int((time.monotonic() - started) * 1000),
        prompt_tokens=response.usage.get("prompt_tokens", 0),
        completion_tokens=response.usage.get("completion_tokens", 0),
        cost_usd=response.cost_usd,
    )
    return {"response": content, "provider": response.provider.value, "model": response.model}


async def _run_workflow_tool(
    db: FirestoreDB,
    workflow: dict,
    execution: dict,
    node: dict,
    tool: dict,
    node_input: dict,
    graph_nodes: dict,
) -> dict:
    gnode = await execution_graph_service.create_node(
        db, execution["id"], NodeType.TOOL_CALL, node_name=tool.get("name")
    )
    graph_nodes[node.get("id")] = gnode
    await execution_graph_service.update_node_status(db, gnode, NodeStatus.RUNNING)
    started = time.monotonic()

    try:
        output = await run_tool(db, tool, params=node_input, execution_id=execution["id"])
        if not output.get("ok"):
            raise ValueError(str(output.get("error") or "Tool call failed"))
        await execution_graph_service.update_node_status(
            db,
            gnode,
            NodeStatus.COMPLETED,
            output_data=output,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return output
    except Exception as exc:
        await execution_graph_service.update_node_status(
            db,
            gnode,
            NodeStatus.FAILED,
            error_message=str(exc),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        raise


async def run_workflow_execution(db: FirestoreDB, execution_id: str) -> None:
    """Walk a workflow DAG in topological order, executing each node."""
    execution = await workflow_service.get_execution(db, execution_id)
    if execution is None or execution.get("status") not in (
        WorkflowExecutionStatus.RUNNING.value,
        WorkflowExecutionStatus.AWAITING_APPROVAL.value,
    ):
        return

    workflow = await workflow_service.get_workflow_by_id(db, execution["workflow_id"])
    if workflow is None:
        await workflow_service.fail_execution(db, execution, "Workflow not found")
        return

    dag = workflow.get("dag_definition") or {}
    nodes = dag.get("nodes") or []
    edges = dag.get("edges") or []
    order = _topological_order(nodes, edges)
    snapshot = execution.get("snapshot") or {}
    context = dict(snapshot.get("context") or {})
    graph_nodes: dict = {}

    # On resume after an approval gate, skip everything up to and including
    # the parked gate (its upstream nodes already ran; context is preserved).
    pending_node = snapshot.get("pending_node")
    if pending_node:
        seen_gate = False
        remaining = []
        for node in order:
            if not seen_gate:
                if node.get("id") == pending_node:
                    seen_gate = True
                continue  # drop nodes already executed before the gate
            remaining.append(node)
        order = remaining

    # The parked approval gate's graph node should read as passed on resume.
    approval_node_id = snapshot.get("approval_node_id")
    gate_marked = False

    try:
        for node in order:
            nid = node.get("id")
            if not nid:
                continue

            # Mark the previously parked approval gate as passed once we resume.
            if approval_node_id and not gate_marked:
                gate_node = await execution_graph_service.get_node_by_id(db, approval_node_id)
                if gate_node is not None:
                    await execution_graph_service.update_node_status(
                        db, gate_node, NodeStatus.COMPLETED, output_data={"approved": True}
                    )
                gate_marked = True

            ntype = (node.get("type") or "").lower()
            # Stop at approval gates: request approval and park execution.
            if ntype in ("approval_gate", "approval", "human_input"):
                gnode = await execution_graph_service.create_node(
                    db, execution["id"], NodeType.APPROVAL_GATE, node_name=node.get("name") or nid
                )
                await execution_graph_service.update_node_status(
                    db, gnode, NodeStatus.AWAITING_INPUT
                )
                await workflow_service.request_approval(db, execution)
                execution["snapshot"] = {
                    "context": context,
                    "pending_node": nid,
                    "approval_node_id": gnode["id"],
                }
                db.set(workflow_service.WORKFLOW_EXECUTIONS, execution["id"], execution)
                return

            output = await _execute_workflow_node(
                db, workflow, execution, node, context, graph_nodes
            )
            context[nid] = output

            # Heartbeat: persist progress so resume/cancel can see where we are.
            execution["snapshot"] = {"context": context}
            db.set(workflow_service.WORKFLOW_EXECUTIONS, execution["id"], execution)

        await workflow_service.complete_execution(
            db, execution, output_data={"results": {k: v for k, v in context.items()}}
        )
    except Exception as exc:
        await workflow_service.fail_execution(db, execution, str(exc))
