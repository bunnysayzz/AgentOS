"""Demo workspace seeder — one-click, realistic first-run experience.

Creates a fully-populated workspace for a user so the product is never an
empty shell on first sign-in: a customer-support agent, a triage workflow, a
few versioned prompt templates, reusable tools, and a conversation memory.
Idempotent: if the user already has a ``demo-workspace`` workspace, returns it
instead of duplicating (same slug + same owner).
"""

import logging

from app.core.db import FirestoreDB
from app.schemas.workspace import WorkspaceCreate
from app.schemas.agent import AgentCreate
from app.schemas.workflow import WorkflowCreate
from app.schemas.prompt import PromptCreate
from app.schemas.tool import ToolCreate
from app.schemas.memory import MemoryEntryCreate
from app.services import workspace_service, agent_service, workflow_service
from app.services import prompt_service, tool_service, memory_service

logger = logging.getLogger(__name__)

DEMO_SLUG = "demo-workspace"


async def _find_existing(db: FirestoreDB, user: dict) -> dict | None:
    """Return the user's existing demo workspace (slug-scoped), if any."""
    for row in db.query("workspaces", "slug", DEMO_SLUG):
        if str(row.get("owner_id") or "") == str(user.get("id") or "") and not row.get("deleted_at"):
            return row
    return None


async def seed_demo_workspace(db: FirestoreDB, user: dict) -> dict:
    """Create (or return) a populated demo workspace for ``user``."""
    existing = await _find_existing(db, user)
    if existing is not None:
        return existing

    # ─── 1. Workspace ────────────────────────────────────────────────
    ws = await workspace_service.create_workspace(
        db,
        WorkspaceCreate(
            name="Demo Workspace",
            slug=DEMO_SLUG,
            description=(
                "A realistic AgentOS workspace: customer-support agent, "
                "triage workflow, versioned prompts, tools and memory. "
                "Explore it, then build your own."
            ),
        ),
        owner=user,
    )
    ws_id = str(ws["id"])

    # ─── 2. Tools ────────────────────────────────────────────────────
    tools = []
    for t in [
        ToolCreate(
            name="Search Knowledge Base",
            slug="search-knowledge-base",
            description="Semantic search across the product knowledge base.",
            tool_type="custom",
            source="builtin",
            schema_definition={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search phrase"},
                },
                "required": ["query"],
            },
            parameters=None,
            auth_type="none",
            is_public=False,
            tags=["search", "knowledge"],
        ),
        ToolCreate(
            name="Get Order Status",
            slug="get-order-status",
            description="Look up a customer order by order ID.",
            tool_type="custom",
            source="builtin",
            schema_definition={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order reference"},
                },
                "required": ["order_id"],
            },
            parameters=None,
            auth_type="none",
            is_public=False,
            tags=["orders", "support"],
        ),
        ToolCreate(
            name="Slack Notify",
            slug="slack-notify",
            description="Send a message to a Slack channel (webhook).",
            tool_type="webhook",
            source="builtin",
            schema_definition={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message text"},
                    "channel": {"type": "string", "description": "Channel name"},
                },
                "required": ["message"],
            },
            parameters=None,
            auth_type="none",
            is_public=False,
            tags=["notify", "slack"],
        ),
    ]:
        tools.append(await tool_service.create_tool(db, t, workspace_id=ws_id))

    tool_ids = [str(t["id"]) for t in tools]
    slack_tool_id = str(tools[2]["id"])  # Slack Notify webhook tool

    # ─── 3. Agents ───────────────────────────────────────────────────
    support_agent = await agent_service.create_agent(
        db,
        ws_id,
        AgentCreate(
            name="Support Hero",
            description="Answers customer questions from the knowledge base and order lookup.",
            system_prompt=(
                "You are Support Hero, a friendly customer-support assistant.\n\n"
                "Rules:\n"
                "- Answer from the knowledge base first; if you don't know, say so.\n"
                "- Use the order-status tool to answer order questions.\n"
                "- Keep replies short, warm and action-oriented.\n"
                "- Never invent order details."
            ),
            model_provider="openai",
            model_name="gpt-4o-mini",
            temperature=0.4,
            max_tokens=1024,
            tool_ids=tool_ids[:2],
        ),
    )

    await agent_service.create_agent(
        db,
        ws_id,
        AgentCreate(
            name="Brief Writer",
            description="Turns raw notes into crisp executive briefs.",
            system_prompt=(
                "You are Brief Writer. Convert the user's notes into a tight "
                "executive brief: headline, key points, recommendation."
            ),
            model_provider="openai",
            model_name="gpt-4o-mini",
            temperature=0.7,
            max_tokens=1024,
            tool_ids=[],
        ),
    )

    # ─── 4. Workflow ─────────────────────────────────────────────────
    # Note: the demo DAG ends in a webhook-style Slack Notify node with no
    # real webhook URL configured — running it will fail at that node by
    # design (it's a structural example, not a live integration).
    await workflow_service.create_workflow(
        db,
        ws_id,
        WorkflowCreate(
            name="Support Triage",
            description=(
                "Classifies an incoming ticket, drafts a response with the "
                "support agent, then notifies Slack for urgent issues."
            ),
            trigger_type="manual",
            dag_definition={
                "nodes": [
                    {
                        "id": "classify",
                        "name": "Classify ticket",
                        "type": "agent",
                        "config": {
                            "agent_id": str(support_agent["id"]),
                            "prompt": "Classify this ticket as {type: billing|product|other}: {{input}}",
                        },
                    },
                    {
                        "id": "respond",
                        "name": "Draft response",
                        "type": "agent",
                        "config": {
                            "agent_id": str(support_agent["id"]),
                            "prompt": "Draft a customer response for: {{input}}",
                        },
                        "depends_on": ["classify"],
                    },
                    {
                        "id": "notify",
                        "name": "Notify Slack",
                        "type": "tool",
                        "config": {"tool_id": slack_tool_id, "message": "New support ticket: {{input}}"},
                        "depends_on": ["respond"],
                    },
                ]
            },
        ),
    )

    # ─── 5. Prompts ──────────────────────────────────────────────────
    for p in [
        PromptCreate(
            name="Customer Reply",
            slug="customer-reply",
            description="Warm, professional customer reply template.",
            prompt_type="template",
            is_public=False,
            tags=["support", "email"],
            initial_content=(
                "Hi {{customer_name}},\n\n"
                "Thanks for reaching out — {{{{agent_name}}}} here. Regarding your "
                "request about {{topic}}: {{resolution}}.\n\n"
                "Is there anything else I can help with?\n\n"
                "Best,\n{{agent_name}}"
            ),
        ),
        PromptCreate(
            name="Weekly Digest",
            slug="weekly-digest",
            description="Summarize a week of activity into a short digest.",
            prompt_type="template",
            is_public=False,
            tags=["reporting"],
            initial_content=(
                "Summarize the following activity into 5 bullet points for a "
                "weekly digest. Highlight wins, risks and asks:\n\n{{activity}}"
            ),
        ),
        PromptCreate(
            name="Code Review Notes",
            slug="code-review-notes",
            description="Extract actionable review feedback from a diff.",
            prompt_type="template",
            is_public=False,
            tags=["engineering"],
            initial_content=(
                "Review this diff and produce: 1) critical issues, 2) style "
                "nits, 3) suggested tests. Be concise:\n\n{{diff}}"
            ),
        ),
    ]:
        await prompt_service.create_prompt(db, p, workspace_id=ws_id)

    # ─── 6. Memory ───────────────────────────────────────────────────
    session_id = f"demo-session-{str(ws['id'])[:8]}"
    for entry in [
        MemoryEntryCreate(
            session_id=session_id,
            role="user",
            content="Our refund policy says refunds are processed within 5 business days.",
            memory_type="conversation",
            metadata={"source": "seed", "topic": "policy"},
        ),
        MemoryEntryCreate(
            session_id=session_id,
            role="assistant",
            content="Got it — I'll reference the 5-business-day refund policy in replies.",
            memory_type="conversation",
            metadata={"source": "seed", "topic": "policy"},
        ),
        MemoryEntryCreate(
            session_id=session_id,
            role="user",
            content="VIP customers (tier gold and above) get priority support and 48h refunds.",
            memory_type="fact",
            metadata={"source": "seed", "topic": "vip"},
        ),
    ]:
        await memory_service.create_entry(db, entry, workspace_id=ws_id, agent_id=str(support_agent["id"]))

    logger.info("Seeded demo workspace %s for user %s", ws_id, user.get("id"))
    return ws
