"""Workflow Engine service - DAG validation, execution lifecycle (Firestore-backed)."""

from app.core.db import FirestoreDB, now_iso, stamp
from app.models.workflow import WorkflowStatus, WorkflowExecutionStatus
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate

WORKFLOWS = "workflows"
WORKFLOW_EXECUTIONS = "workflow_executions"


# ─── Errors ──────────────────────────────────────────


class WorkflowError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class WorkflowNotFoundError(WorkflowError):
    def __init__(self):
        super().__init__("Workflow not found", status_code=404)


class InvalidDAGError(WorkflowError):
    pass


# ─── DAG Validation ────────────────────────────────


def validate_dag(dag: dict | None) -> list[str]:
    """Validate a DAG definition. Returns list of validation errors (empty = valid)."""
    errors = []
    if not dag:
        return ["DAG definition is required"]

    nodes = dag.get("nodes", [])
    edges = dag.get("edges", [])

    if not nodes:
        errors.append("DAG must have at least one node")
        return errors

    node_ids = set()
    for i, node in enumerate(nodes):
        nid = node.get("id")
        if not nid:
            errors.append(f"Node {i} is missing an 'id' field")
        elif nid in node_ids:
            errors.append(f"Duplicate node id: {nid}")
        else:
            node_ids.add(nid)

        if not node.get("type"):
            errors.append(f"Node {nid or i} is missing a 'type' field")

    for i, edge in enumerate(edges):
        source = edge.get("source")
        target = edge.get("target")
        if source and source not in node_ids:
            errors.append(f"Edge {i}: source '{source}' not found in nodes")
        if target and target not in node_ids:
            errors.append(f"Edge {i}: target '{target}' not found in nodes")

    if node_ids and _has_cycle(nodes, edges):
        errors.append("DAG contains a cycle — workflows must be acyclic")

    if edges:
        connected = set()
        for edge in edges:
            if edge.get("source"):
                connected.add(edge["source"])
            if edge.get("target"):
                connected.add(edge["target"])
        disconnected = node_ids - connected
        if len(disconnected) != len(node_ids):
            for nid in disconnected:
                errors.append(f"Node '{nid}' is disconnected (no incoming or outgoing edges)")

    return errors


def _has_cycle(nodes: list[dict], edges: list[dict]) -> bool:
    """Detect cycles in a directed graph using DFS."""
    adj = {n["id"]: [] for n in nodes}
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src and tgt:
            adj[src].append(tgt)

    visited = set()
    rec_stack = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.discard(node)
        return False

    for node in adj:
        if node not in visited:
            if dfs(node):
                return True
    return False


# ─── Workflow CRUD ────────────────────────────────


async def create_workflow(db: FirestoreDB, workspace_id: str, wf_in: WorkflowCreate) -> dict:
    """Create a new workflow with DAG validation."""
    if wf_in.dag_definition:
        errors = validate_dag(wf_in.dag_definition)
        if errors:
            raise InvalidDAGError("; ".join(errors))

    workflow = stamp({
        "workspace_id": str(workspace_id),
        "name": wf_in.name,
        "description": wf_in.description,
        "dag_definition": wf_in.dag_definition,
        "trigger_type": wf_in.trigger_type,
        "trigger_config": wf_in.trigger_config,
        "schedule_cron": wf_in.schedule_cron,
        "timeout_seconds": wf_in.timeout_seconds,
        "status": WorkflowStatus.DRAFT.value,
        "version": 1,
    })
    db.add(WORKFLOWS, workflow)
    return workflow


async def get_workflow_by_id(db: FirestoreDB, workflow_id: str) -> dict | None:
    workflow = db.get(WORKFLOWS, str(workflow_id))
    if workflow is None or workflow.get("deleted_at"):
        return None
    return workflow


async def list_workspace_workflows(
    db: FirestoreDB, workspace_id: str, page: int = 1, page_size: int = 50
) -> tuple[list[dict], int]:
    rows = [
        r for r in db.query(WORKFLOWS, "workspace_id", str(workspace_id))
        if not r.get("deleted_at")
    ]
    rows.sort(key=lambda r: (r.get("updated_at") or "", r.get("created_at") or ""), reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def update_workflow(db: FirestoreDB, workflow: dict, wf_in: WorkflowUpdate) -> dict:
    update_data = wf_in.model_dump(exclude_unset=True)

    if "dag_definition" in update_data and update_data["dag_definition"]:
        errors = validate_dag(update_data["dag_definition"])
        if errors:
            raise InvalidDAGError("; ".join(errors))
        workflow["version"] = (workflow.get("version") or 1) + 1

    for field, value in update_data.items():
        workflow[field] = value

    db.set(WORKFLOWS, workflow["id"], workflow)
    return workflow


async def delete_workflow(db: FirestoreDB, workflow: dict) -> None:
    workflow["deleted_at"] = now_iso()
    workflow["status"] = WorkflowStatus.ARCHIVED.value
    db.set(WORKFLOWS, workflow["id"], workflow)


# ─── Webhook triggers ────────────────────────────


def _gen_webhook_token() -> str:
    """Generate a URL-safe webhook secret."""
    import secrets

    return secrets.token_urlsafe(24)


async def get_or_create_webhook_token(db: FirestoreDB, workflow: dict) -> str:
    """Return the workflow's webhook token, generating + persisting one if absent.

    The token is stored BOTH at the top level (``webhook_token`` — enables an
    indexed Firestore lookup) and inside ``trigger_config`` for display.
    """
    token = workflow.get("webhook_token")
    if not token:
        token = _gen_webhook_token()
        workflow["webhook_token"] = token
        cfg = dict(workflow.get("trigger_config") or {})
        cfg["webhook_token"] = token
        workflow["trigger_config"] = cfg
        db.set(WORKFLOWS, workflow["id"], workflow)
    return token


async def find_workflow_by_webhook_token(db: FirestoreDB, token: str) -> dict | None:
    """Find an active workflow whose webhook token matches (used by the
    unauthenticated inbound webhook route — the token IS the secret).

    Uses an indexed top-level query; falls back to a scan for legacy rows that
    only carry the token inside ``trigger_config``.
    """
    for wf in db.query(WORKFLOWS, "webhook_token", token):
        if not wf.get("deleted_at") and wf.get("status") == WorkflowStatus.ACTIVE.value:
            return wf
    # Legacy fallback: rows created before the top-level field existed.
    for wf in db.query(WORKFLOWS):
        if wf.get("deleted_at") or wf.get("status") != WorkflowStatus.ACTIVE.value:
            continue
        cfg = wf.get("trigger_config") or {}
        if cfg.get("webhook_token") == token and not wf.get("webhook_token"):
            return wf
    return None


# ─── Execution Lifecycle ──────────────────────────


async def create_execution(
    db: FirestoreDB, workflow: dict, input_data: dict | None = None,
    triggered_by: str | None = None,
) -> dict:
    if workflow.get("status") != WorkflowStatus.ACTIVE.value:
        raise WorkflowError(f"Cannot execute workflow in '{workflow.get('status')}' status")

    execution = stamp({
        "workflow_id": workflow["id"],
        "status": WorkflowExecutionStatus.PENDING.value,
        "input_data": input_data,
        "triggered_by": triggered_by or "user",
        "trigger_event": None,
        "output_data": None,
        "error_message": None,
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
        "checkpoint_path": None,
        "snapshot": None,
    })
    db.add(WORKFLOW_EXECUTIONS, execution)
    return execution


async def get_execution(db: FirestoreDB, execution_id: str) -> dict | None:
    return db.get(WORKFLOW_EXECUTIONS, str(execution_id))


async def list_executions(
    db: FirestoreDB, workflow_id: str, page: int = 1, page_size: int = 50
) -> tuple[list[dict], int]:
    rows = db.query(WORKFLOW_EXECUTIONS, "workflow_id", str(workflow_id))
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def start_execution(db: FirestoreDB, execution: dict) -> dict:
    if execution.get("status") != WorkflowExecutionStatus.PENDING.value:
        raise WorkflowError(f"Cannot start execution in '{execution.get('status')}' status")
    execution["status"] = WorkflowExecutionStatus.RUNNING.value
    execution["started_at"] = now_iso()
    db.set(WORKFLOW_EXECUTIONS, execution["id"], execution)
    return execution


async def complete_execution(db: FirestoreDB, execution: dict, output_data: dict | None = None) -> dict:
    if execution.get("status") != WorkflowExecutionStatus.RUNNING.value:
        raise WorkflowError(f"Cannot complete execution in '{execution.get('status')}' status")
    execution["status"] = WorkflowExecutionStatus.COMPLETED.value
    execution["completed_at"] = now_iso()
    execution["output_data"] = output_data
    if execution.get("started_at"):
        from datetime import datetime, timezone
        try:
            start = datetime.fromisoformat(execution["started_at"].replace("Z", "+00:00"))
            execution["duration_ms"] = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        except Exception:
            pass
    db.set(WORKFLOW_EXECUTIONS, execution["id"], execution)
    return execution


async def fail_execution(db: FirestoreDB, execution: dict, error: str) -> dict:
    if execution.get("status") not in (
        WorkflowExecutionStatus.RUNNING.value,
        WorkflowExecutionStatus.PENDING.value,
    ):
        raise WorkflowError(f"Cannot fail execution in '{execution.get('status')}' status")
    execution["status"] = WorkflowExecutionStatus.FAILED.value
    execution["completed_at"] = now_iso()
    execution["error_message"] = error
    if execution.get("started_at"):
        from datetime import datetime, timezone
        try:
            start = datetime.fromisoformat(execution["started_at"].replace("Z", "+00:00"))
            execution["duration_ms"] = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        except Exception:
            pass
    db.set(WORKFLOW_EXECUTIONS, execution["id"], execution)
    return execution


async def pause_execution(db: FirestoreDB, execution: dict) -> dict:
    if execution.get("status") != WorkflowExecutionStatus.RUNNING.value:
        raise WorkflowError(f"Cannot pause execution in '{execution.get('status')}' status")
    execution["status"] = WorkflowExecutionStatus.PAUSED.value
    db.set(WORKFLOW_EXECUTIONS, execution["id"], execution)
    return execution


async def resume_execution(db: FirestoreDB, execution: dict) -> dict:
    if execution.get("status") != WorkflowExecutionStatus.PAUSED.value:
        raise WorkflowError(f"Cannot resume execution in '{execution.get('status')}' status")
    execution["status"] = WorkflowExecutionStatus.RUNNING.value
    db.set(WORKFLOW_EXECUTIONS, execution["id"], execution)
    return execution


async def cancel_execution(db: FirestoreDB, execution: dict) -> dict:
    if execution.get("status") not in (
        WorkflowExecutionStatus.PENDING.value,
        WorkflowExecutionStatus.RUNNING.value,
        WorkflowExecutionStatus.AWAITING_APPROVAL.value,
    ):
        raise WorkflowError(f"Cannot cancel execution in '{execution.get('status')}' status")
    execution["status"] = WorkflowExecutionStatus.CANCELLED.value
    execution["completed_at"] = now_iso()
    if execution.get("started_at"):
        from datetime import datetime, timezone
        try:
            start = datetime.fromisoformat(execution["started_at"].replace("Z", "+00:00"))
            execution["duration_ms"] = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        except Exception:
            pass
    db.set(WORKFLOW_EXECUTIONS, execution["id"], execution)
    return execution


async def request_approval(db: FirestoreDB, execution: dict) -> dict:
    execution["status"] = WorkflowExecutionStatus.AWAITING_APPROVAL.value
    db.set(WORKFLOW_EXECUTIONS, execution["id"], execution)
    return execution


async def approve_execution(db: FirestoreDB, execution: dict) -> dict:
    if execution.get("status") != WorkflowExecutionStatus.AWAITING_APPROVAL.value:
        raise WorkflowError(f"Cannot approve execution in '{execution.get('status')}' status")
    wf = await get_workflow_by_id(db, execution["workflow_id"])
    if wf and wf.get("status") != WorkflowStatus.ACTIVE.value:
        raise WorkflowError(f"Cannot approve — workflow is '{wf.get('status')}', must be 'active'")
    execution["status"] = WorkflowExecutionStatus.RUNNING.value
    db.set(WORKFLOW_EXECUTIONS, execution["id"], execution)
    return execution
