"""Seed a full "architecture studio" workspace for stfuazzo@gmail.com.

Writes directly to Cloud Firestore through the app's service layer, so every
document matches the public API contract (same collections, same field names,
same encryption as the running backend). Run from the backend dir:

    .venv/bin/python -m app.scripts.seed_architecture

Provider API keys are read from a local .env (path configurable via
PRPILOT_ENV) and stored encrypted with the app's ENCRYPTION_KEY — the same key
the deployed backend uses, so the keys decrypt in production.
"""

import asyncio
import logging
import os
from pathlib import Path

from app.core.db import FirestoreDB
from app.models.mcp import LLMProvider
from app.models.tool import ToolType
from app.models.workflow import WorkflowStatus
from app.models.agent import AgentStatus
from app.schemas.agent import AgentCreate
from app.schemas.workflow import WorkflowCreate
from app.schemas.workspace import WorkspaceCreate
from app.schemas.mcp import ProviderConfigCreate
from app.schemas.prompt import PromptCreate, PromptVersionCreate
from app.schemas.tool import ToolCreate
from app.schemas.secret import SecretCreate
from app.schemas.artifact import ArtifactCreate
from app.schemas.memory import MemoryEntryCreate

from app.services import (
    workspace_service,
    agent_service,
    workflow_service,
    prompt_service,
    tool_service,
    secret_service,
    artifact_service,
    memory_service,
    provider_service,
    auth_service,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("seed_architecture")

TARGET_EMAIL = os.environ.get("SEED_EMAIL", "stfuazzo@gmail.com")
PRPILOT_ENV = os.environ.get("PRPILOT_ENV", str(Path.home() / "Desktop" / "Batman" / "tuba" / "prpilot" / ".env"))


def load_keys(path: str) -> dict:
    """Load API keys from a dotenv-style file (does not print them)."""
    keys = {}
    p = Path(path).expanduser()
    if not p.exists():
        logger.warning(f"prpilot env not found at {p} — providers will be skipped")
        return keys
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and v and not v.startswith(("#", "-----")):
            keys[k] = v
    return keys


async def main() -> None:
    db = FirestoreDB()

    # ─── 1. User ──────────────────────────────────────────────────────
    user = auth_service.get_user_by_email(db, TARGET_EMAIL)
    if user is None:
        logger.info(f"User {TARGET_EMAIL} not found — creating…")
        user = auth_service.get_or_create_user_from_firebase(db, {
            "uid": "seed-arch",
            "email": TARGET_EMAIL,
            "name": "Azharuddin",
            "picture": None,
        })
    logger.info(f"✅ User: {user['email']} (id {user['id']})")

    # ─── 2. Workspace ─────────────────────────────────────────────────
    existing = await workspace_service.get_workspace_by_slug(db, "architecture-studio")
    if existing is not None:
        ws = existing
        logger.info(f"Workspace already exists — reusing {ws['name']} ({ws['id']})")
    else:
        ws = await workspace_service.create_workspace(
            db,
            WorkspaceCreate(
                name="Architecture Studio",
                slug="architecture-studio",
                description=(
                    "Full-stack agentic architecture: orchestrated agents, "
                    "approval-based workflows, prompt registry, tool chain and "
                    "shared memory — a production blueprint for stfuazzo@gmail.com."
                ),
            ),
            owner=user,
        )
        logger.info(f"✅ Workspace created: {ws['name']} ({ws['id']})")
        ws["settings"] = {"environment": "production", "max_concurrent_agents": 10, "enable_telemetry": True}
        db.set(workspace_service.WORKSPACES, ws["id"], ws)
    ws_id = ws["id"]

    # ─── 3. Providers (real keys, encrypted with app ENCRYPTION_KEY) ──
    # base_url is critical: route_chat_completion falls back to OpenAI's
    # endpoint when a config lacks it, which would 401 for groq/cerebras keys.
    from app.services.provider_metadata import get_provider_metadata

    keys = load_keys(PRPILOT_ENV)
    provider_plan: list[tuple[LLMProvider, str, str]] = []
    if keys.get("GROQ_API_KEY"):
        provider_plan.append((LLMProvider.GROQ, keys["GROQ_API_KEY"], "llama-3.3-70b-versatile"))
    if keys.get("CEREBRAS_API_KEY"):
        provider_plan.append((LLMProvider.CEREBRAS, keys["CEREBRAS_API_KEY"], "gpt-oss-120b"))
    if keys.get("GEMINI_API_KEY"):
        provider_plan.append((LLMProvider.GOOGLE, keys["GEMINI_API_KEY"], "gemini-2.0-flash"))
    if keys.get("LLMAPI_API_KEY"):
        provider_plan.append((LLMProvider.LLMAPI, keys["LLMAPI_API_KEY"], "gpt-4o"))

    configured_providers: list[str] = []
    for provider, api_key, model in provider_plan:
        meta = get_provider_metadata(provider)
        await provider_service.upsert_provider_config(
            db,
            ProviderConfigCreate(
                provider=provider,
                api_key=api_key,
                default_model=model,
                base_url=meta.get("base_url") or None,
            ),
        )
        configured_providers.append(provider.value)
        logger.info(f"✅ Provider configured: {provider.value} (default {model}, base_url {meta.get('base_url')})")

    if not configured_providers:
        logger.warning("⚠️ No provider keys found — agents will still be created but cannot call LLMs yet.")

    # ─── 4. Tools (built first so agents can reference tool_ids) ──────
    tools_plan = [
        ToolCreate(
            name="GitHub PR Fetcher", slug="github-pr-fetcher",
            description="Fetch a GitHub pull request diff and metadata by number.",
            tool_type=ToolType.WEBHOOK, source="https://api.github.com",
            schema_definition={"type": "object", "properties": {"repo": {"type": "string"}, "pr_number": {"type": "integer"}}},
            parameters={"method": "GET", "url_template": "/repos/{repo}/pulls/{pr_number}"},
            is_public=False, tags=["github", "devops"],
        ),
        ToolCreate(
            name="Web Search", slug="web-search",
            description="Search the public web and return top results with snippets.",
            tool_type=ToolType.CUSTOM, source="https://duckduckgo.com/html/?q={query}",
            schema_definition={"type": "object", "properties": {"query": {"type": "string"}}},
            parameters={"method": "GET"}, is_public=False, tags=["research"],
        ),
        ToolCreate(
            name="SQL Query Runner", slug="sql-query-runner",
            description="Execute a read-only SQL query against the analytics warehouse.",
            tool_type=ToolType.CUSTOM, source="postgresql://analytics",
            schema_definition={"type": "object", "properties": {"query": {"type": "string"}}},
            parameters={"method": "POST", "read_only": True}, is_public=False, tags=["data", "analytics"],
        ),
        ToolCreate(
            name="Slack Notifier", slug="slack-notifier",
            description="Post a message to a Slack channel.",
            tool_type=ToolType.CUSTOM, source="https://slack.com/api/chat.postMessage",
            schema_definition={"type": "object", "properties": {"channel": {"type": "string"}, "text": {"type": "string"}}},
            parameters={"method": "POST"}, is_public=False, tags=["notifications"],
        ),
    ]
    tool_ids: dict[str, str] = {}
    for t in tools_plan:
        existing_tool = await tool_service.get_tool_by_slug(db, t.slug)
        if existing_tool is not None:
            tool_ids[t.slug] = existing_tool["id"]
            logger.info(f"Tool exists: {t.name}")
            continue
        tool = await tool_service.create_tool(db, t, workspace_id=ws_id)
        tool_ids[t.slug] = tool["id"]
        logger.info(f"✅ Tool: {t.name} ({tool['id']})")

    # ─── 5. Agents ────────────────────────────────────────────────────
    def pick(p: str) -> tuple[str, str]:
        if p in configured_providers:
            return p, [m for prov, _, m in provider_plan if prov.value == p][0]
        return (configured_providers[0], [m for _, _, m in provider_plan][0]) if configured_providers else ("openai", "gpt-4o-mini")

    groq_provider, groq_model = pick("groq")
    gemini_provider, gemini_model = pick("google")
    cerebras_provider, cerebras_model = pick("cerebras")
    llmapi_provider, llmapi_model = pick("llmapi")

    agents_plan = [
        AgentCreate(
            name="Orchestrator",
            description="Plans tasks, routes work to specialist agents, and synthesizes final answers.",
            system_prompt=(
                "You are the Orchestrator of an agentic architecture. Break the user's request "
                "into steps, delegate to the right specialist (Research, Writer, Code Reviewer, "
                "Data Analyst), and merge their outputs into one coherent final answer."
            ),
            model_provider=groq_provider, model_name=groq_model, temperature=0.3, max_tokens=4096,
            tool_ids=[tool_ids["web-search"]],
        ),
        AgentCreate(
            name="Research Analyst",
            description="Deep web research: gathers sources, extracts facts, and cites findings.",
            system_prompt=(
                "You are a Research Analyst. Use the Web Search tool to find credible sources, "
                "extract key facts with citations, and return a structured research brief."
            ),
            model_provider=gemini_provider, model_name=gemini_model, temperature=0.2, max_tokens=4096,
            tool_ids=[tool_ids["web-search"]],
        ),
        AgentCreate(
            name="Content Writer",
            description="Drafts long-form content from a research brief in the brand voice.",
            system_prompt=(
                "You are a Content Writer. Turn research briefs into polished long-form content: "
                "clear structure, strong headlines, and a confident, professional voice."
            ),
            model_provider=groq_provider, model_name=groq_model, temperature=0.7, max_tokens=8192,
            tool_ids=[],
        ),
        AgentCreate(
            name="Code Reviewer",
            description="Reviews pull requests for bugs, security flaws and style, then posts comments.",
            system_prompt=(
                "You are a Senior Code Reviewer. Analyze PR diffs fetched by the GitHub PR Fetcher, "
                "flag bugs, security issues, and style violations with line-level suggestions."
            ),
            model_provider=cerebras_provider, model_name=cerebras_model, temperature=0.2, max_tokens=4096,
            tool_ids=[tool_ids["github-pr-fetcher"], tool_ids["slack-notifier"]],
        ),
        AgentCreate(
            name="Data Analyst",
            description="Runs read-only SQL analytics and explains trends in plain language.",
            system_prompt=(
                "You are a Data Analyst. Use the SQL Query Runner for read-only queries, interpret "
                "the results, and explain trends with charts-ready summaries."
            ),
            model_provider=llmapi_provider, model_name=llmapi_model, temperature=0.1, max_tokens=4096,
            tool_ids=[tool_ids["sql-query-runner"]],
        ),
    ]
    agent_ids: dict[str, str] = {}
    for a in agents_plan:
        # idempotent: skip if an agent with this name already exists in the workspace
        existing_agents, _ = await agent_service.list_workspace_agents(db, ws_id)
        dup = next((x for x in existing_agents if x.get("name") == a.name and not x.get("deleted_at")), None)
        if dup is not None:
            agent_ids[a.name] = dup["id"]
            logger.info(f"Agent exists: {a.name}")
            continue
        agent = await agent_service.create_agent(db, ws_id, a)
        agent["status"] = AgentStatus.ACTIVE.value
        db.set(agent_service.AGENTS, agent["id"], agent)
        agent_ids[a.name] = agent["id"]
        logger.info(f"✅ Agent: {a.name} ({agent['id']})")

    # ─── 6. Prompts ───────────────────────────────────────────────────
    prompts_plan = [
        PromptCreate(
            name="Orchestrator System Prompt", slug="orchestrator_system",
            description="System prompt for the Orchestrator agent.",
            tags=["agent", "system"], initial_content=(
                "You are the Orchestrator of an agentic architecture. Break the user's request "
                "into steps, delegate to the right specialist, and merge outputs into one coherent "
                "final answer.\n\nTask: {{task}}"
            ),
        ),
        PromptCreate(
            name="Research Brief Template", slug="research_brief",
            description="Template for structured research briefs.",
            tags=["research"], initial_content=(
                "Research the following topic and return a brief with: Summary, Key Findings "
                "(with sources), and Open Questions.\n\nTopic: {{topic}}"
            ),
        ),
        PromptCreate(
            name="PR Review Template", slug="pr_review",
            description="Template for line-level code review comments.",
            tags=["code-review"], initial_content=(
                "Review the following diff. For each issue, give file, line, severity "
                "(critical|warning|nit), and a suggested fix.\n\nDiff:\n{{diff}}"
            ),
        ),
    ]
    for p in prompts_plan:
        existing_prompts, _ = await prompt_service.list_workspace_prompts(db, ws_id)
        dup = next((x for x in existing_prompts if x.get("slug") == p.slug and not x.get("deleted_at")), None)
        if dup is not None:
            logger.info(f"Prompt exists: {p.name}")
            continue
        prompt = await prompt_service.create_prompt(db, p, workspace_id=ws_id)
        logger.info(f"✅ Prompt: {p.name} ({prompt['id']})")

    # ─── 7. Workflows (valid DAGs) ────────────────────────────────────
    workflows_plan = [
        WorkflowCreate(
            name="Research-to-Publish Pipeline",
            description="Research a topic, draft content, review it, then notify the channel.",
            trigger_type="manual",
            dag_definition={
                "nodes": [
                    {"id": "research", "type": "agent", "name": "Research Analyst"},
                    {"id": "draft", "type": "agent", "name": "Content Writer"},
                    {"id": "review", "type": "agent", "name": "Code Reviewer"},
                    {"id": "notify", "type": "tool", "name": "Slack Notifier"},
                ],
                "edges": [
                    {"source": "research", "target": "draft"},
                    {"source": "draft", "target": "review"},
                    {"source": "review", "target": "notify"},
                ],
            },
            timeout_seconds=900,
        ),
        WorkflowCreate(
            name="Automated PR Review",
            description="On pull_request.opened: fetch the diff, review it, post a summary.",
            trigger_type="webhook",
            trigger_config={"event": "pull_request.opened"},
            dag_definition={
                "nodes": [
                    {"id": "fetch", "type": "tool", "name": "GitHub PR Fetcher"},
                    {"id": "review", "type": "agent", "name": "Code Reviewer"},
                    {"id": "post", "type": "tool", "name": "Slack Notifier"},
                ],
                "edges": [
                    {"source": "fetch", "target": "review"},
                    {"source": "review", "target": "post"},
                ],
            },
            timeout_seconds=600,
        ),
        WorkflowCreate(
            name="Daily Intelligence Brief",
            description="Scheduled every morning: research trending topics and post a brief.",
            trigger_type="schedule",
            schedule_cron="0 8 * * *",
            dag_definition={
                "nodes": [
                    {"id": "research", "type": "agent", "name": "Research Analyst"},
                    {"id": "summarize", "type": "agent", "name": "Orchestrator"},
                    {"id": "notify", "type": "tool", "name": "Slack Notifier"},
                ],
                "edges": [
                    {"source": "research", "target": "summarize"},
                    {"source": "summarize", "target": "notify"},
                ],
            },
            timeout_seconds=600,
        ),
    ]
    for w in workflows_plan:
        existing_wfs, _ = await workflow_service.list_workspace_workflows(db, ws_id)
        dup = next((x for x in existing_wfs if x.get("name") == w.name and not x.get("deleted_at")), None)
        if dup is not None:
            logger.info(f"Workflow exists: {w.name}")
            continue
        wf = await workflow_service.create_workflow(db, ws_id, w)
        wf["status"] = WorkflowStatus.ACTIVE.value
        db.set(workflow_service.WORKFLOWS, wf["id"], wf)
        logger.info(f"✅ Workflow: {w.name} ({wf['id']})")

    # ─── 8. Secrets (encrypted values) ────────────────────────────────
    secrets_plan = [
        ("GROQ_API_KEY", keys.get("GROQ_API_KEY", "")),
        ("GEMINI_API_KEY", keys.get("GEMINI_API_KEY", "")),
        ("CEREBRAS_API_KEY", keys.get("CEREBRAS_API_KEY", "")),
    ]
    for name, value in secrets_plan:
        if not value:
            continue
        existing_secrets, _ = await secret_service.list_workspace_secrets(db, ws_id)
        dup = next((x for x in existing_secrets if x.get("slug") == name.lower() and not x.get("deleted_at")), None)
        if dup is not None:
            logger.info(f"Secret exists: {name}")
            continue
        secret = await secret_service.create_secret(
            db, ws_id, SecretCreate(name=name, slug=name.lower(), value=value,
                                    description=f"{name} for Architecture Studio", environment="production"),
        )
        logger.info(f"✅ Secret stored (encrypted): {name} ({secret['id']})")

    # ─── 9. Artifacts ─────────────────────────────────────────────────
    artifacts_plan = [
        ArtifactCreate(
            name="architecture-blueprint.json", content_type="application/json",
            metadata={"kind": "architecture", "version": "1.0",
                      "note": "Agentic architecture blueprint for Architecture Studio"},
        ),
        ArtifactCreate(
            name="system-topology.md", content_type="text/markdown",
            metadata={"kind": "diagram", "version": "1.0",
                      "note": "Topology: Orchestrator -> Research/Writer/Reviewer/DataAnalyst -> Tools"},
        ),
    ]
    for a in artifacts_plan:
        existing_arts, _ = await artifact_service.list_workspace_artifacts(db, ws_id)
        dup = next((x for x in existing_arts if x.get("name") == a.name and not x.get("deleted_at")), None)
        if dup is not None:
            logger.info(f"Artifact exists: {a.name}")
            continue
        data = a.name.encode()
        art = await artifact_service.create_artifact(db, ws_id, a, data=data)
        logger.info(f"✅ Artifact: {a.name} ({art['id']})")

    # ─── 10. Memory ───────────────────────────────────────────────────
    memory_plan = [
        MemoryEntryCreate(role="system", content="Workspace architecture: orchestrator + 4 specialists with shared memory.", memory_type="workspace", session_id="arch-ws"),
        MemoryEntryCreate(role="user", content="Preferred stack: FastAPI, Firebase Auth + Firestore, React + Tailwind.", memory_type="preference", session_id="arch-ws"),
        MemoryEntryCreate(role="user", content="Deploy target: Render with Docker, single service.", memory_type="preference", session_id="arch-ws"),
    ]
    for m in memory_plan:
        await memory_service.create_entry(db, m, workspace_id=ws_id)
        logger.info(f"✅ Memory entry stored ({m.memory_type})")

    # ─── 11. Summary ──────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("SEED COMPLETE — Architecture Studio")
    logger.info(f"  workspace : {ws['name']} ({ws_id})")
    logger.info(f"  providers : {', '.join(configured_providers) if configured_providers else 'none'}")
    logger.info(f"  agents    : {', '.join(agent_ids.keys())}")
    logger.info(f"  workflows : {len(workflows_plan)}")
    logger.info(f"  tools     : {', '.join(tool_ids.keys())}")
    logger.info(f"  prompts   : {len(prompts_plan)}")
    logger.info(f"  secrets   : {len(secrets_plan)}")
    logger.info(f"  artifacts : {len(artifacts_plan)}")
    logger.info(f"  memory    : {len(memory_plan)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
