"""Execution Graph service — node-level execution tracing (Firestore-backed)."""

from app.core.db import FirestoreDB, now_iso, stamp
from app.models.execution_graph import NodeStatus

NODES = "execution_graph_nodes"


# ─── Errors ──────────────────────────────────────────


class ExecutionGraphError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NodeNotFoundError(ExecutionGraphError):
    def __init__(self):
        super().__init__("Execution graph node not found", status_code=404)


# ─── CRUD ────────────────────────────────────────────


async def create_node(
    db: FirestoreDB,
    execution_id: str,
    node_type,
    node_name: str | None = None,
    parent_node_id: str | None = None,
    input_data: dict | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
) -> dict:
    """Create a new node in the execution graph."""
    node = stamp({
        "execution_id": str(execution_id),
        "parent_node_id": str(parent_node_id) if parent_node_id else None,
        "node_type": node_type.value if hasattr(node_type, "value") else str(node_type),
        "node_name": node_name,
        "status": NodeStatus.PENDING.value,
        "input_data": input_data,
        "output_data": None,
        "error_message": None,
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
        "model_provider": model_provider,
        "model_name": model_name,
        "prompt_tokens": None,
        "completion_tokens": None,
        "cost_usd": None,
        "checkpoint_path": None,
    })
    db.add(NODES, node)
    return node


async def get_node_by_id(db: FirestoreDB, node_id: str) -> dict | None:
    return db.get(NODES, str(node_id))


async def update_node_status(
    db: FirestoreDB,
    node: dict,
    status,
    output_data: dict | None = None,
    error_message: str | None = None,
    duration_ms: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    cost_usd: float | None = None,
    checkpoint_path: str | None = None,
) -> dict:
    """Update node status and execution metrics."""
    status_value = status.value if hasattr(status, "value") else str(status)
    node["status"] = status_value

    if output_data is not None:
        node["output_data"] = output_data
    if error_message is not None:
        node["error_message"] = error_message
    if duration_ms is not None:
        node["duration_ms"] = duration_ms
    if prompt_tokens is not None:
        node["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        node["completion_tokens"] = completion_tokens
    if cost_usd is not None:
        node["cost_usd"] = cost_usd
    if checkpoint_path is not None:
        node["checkpoint_path"] = checkpoint_path

    # Timing
    if status_value == NodeStatus.RUNNING.value and node.get("started_at") is None:
        node["started_at"] = now_iso()
    elif status_value in (
        NodeStatus.COMPLETED.value,
        NodeStatus.FAILED.value,
        NodeStatus.CANCELLED.value,
    ):
        node["completed_at"] = now_iso()

    db.set(NODES, node["id"], node)
    return node


async def list_execution_nodes(db: FirestoreDB, execution_id: str) -> list[dict]:
    """Get all nodes for an execution, ordered by creation."""
    rows = db.query(NODES, "execution_id", str(execution_id))
    rows.sort(key=lambda r: r.get("created_at") or "")
    return rows


async def get_execution_graph(db: FirestoreDB, execution_id: str) -> tuple[list[dict], dict]:
    """Get full execution graph with summary stats."""
    nodes = await list_execution_nodes(db, execution_id)

    total_duration = sum(r.get("duration_ms") or 0 for r in nodes)
    total_cost = sum(r.get("cost_usd") or 0 for r in nodes)
    total_tokens = sum((r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0) for r in nodes)

    stats = {
        "total_duration_ms": total_duration,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "node_count": len(nodes),
        "by_status": {},
        "by_type": {},
    }

    for n in nodes:
        status = n.get("status") or "pending"
        ntype = n.get("node_type") or "unknown"
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        stats["by_type"][ntype] = stats["by_type"].get(ntype, 0) + 1

    return nodes, stats


async def get_node_children(db: FirestoreDB, parent_node_id: str) -> list[dict]:
    """Get child nodes of a given node."""
    rows = db.query(NODES, "parent_node_id", str(parent_node_id))
    rows.sort(key=lambda r: r.get("created_at") or "")
    return rows
