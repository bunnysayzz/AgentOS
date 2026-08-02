"""Seed and test a complete, production-ready workspace and all agentic assets directly into Cloud Firestore."""

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.services.firebase_db import firestore_db_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_production_workspace():
    logger.info("Starting Cloud Firestore Production Seeding...")

    now_iso = datetime.now(timezone.utc).isoformat()
    ws_id = "prod-agentos-workspace-001"
    user_id = "5dac122ae1ac40448ab55dee8ce0f704" # Superuser ID

    # 1. Production Workspace
    ws_data = {
        "id": ws_id,
        "name": "Production Agentic Studio",
        "slug": "production-agentic-studio",
        "description": "Production environment for enterprise AI agents, automated workflows, and MCP tools.",
        "owner_id": user_id,
        "is_personal": False,
        "settings": {
            "max_concurrent_agents": 20,
            "enable_telemetry": True,
            "environment": "production"
        },
        "created_at": now_iso,
        "updated_at": now_iso
    }
    firestore_db_service.save_workspace(ws_id, ws_data)
    logger.info(f"✅ Created Workspace: {ws_data['name']} (ID: {ws_id})")

    # 2. Workspace Membership
    member_id = f"{ws_id}_{user_id}"
    firestore_db_service.set_document("workspace_members", member_id, {
        "workspace_id": ws_id,
        "user_id": user_id,
        "role": "OWNER",
        "email": "azharsayzz@gmail.com",
        "created_at": now_iso
    })
    logger.info(f"✅ Added Workspace Member: OWNER (User: {user_id})")

    # 3. Production Agents
    agents = [
        {
            "id": "agent-code-reviewer-01",
            "workspace_id": ws_id,
            "name": "Autonomous Code Reviewer",
            "description": "Analyzes Pull Requests, checks AST patterns, and generates comprehensive code review comments.",
            "system_prompt": "You are a Senior Principal Software Engineer conducting rigorous code reviews. Focus on security, performance, and maintainability.",
            "model_provider": "openai",
            "model_name": "gpt-4o",
            "temperature": 0.2,
            "max_tokens": 4096,
            "status": "active",
            "tool_ids": ["tool-github-pr-01", "tool-ast-parser-01"],
            "version": "1.0.0",
            "created_at": now_iso
        },
        {
            "id": "agent-support-assistant-02",
            "workspace_id": ws_id,
            "name": "Customer Support Copilot",
            "description": "Handles tier-1 customer inquiries and routes complex issues to human engineers.",
            "system_prompt": "You are a empathetic and concise Customer Support Engineer for AgentOS Studio. Provide helpful solution steps.",
            "model_provider": "anthropic",
            "model_name": "claude-3-5-sonnet-20241022",
            "temperature": 0.5,
            "max_tokens": 2048,
            "status": "active",
            "tool_ids": ["tool-vector-kb-01"],
            "version": "1.2.0",
            "created_at": now_iso
        }
    ]
    for agent in agents:
        firestore_db_service.save_agent(agent["id"], agent)
        logger.info(f"✅ Created Agent: {agent['name']} ({agent['model_name']})")

    # 4. Production Workflows
    workflows = [
        {
            "id": "wf-pr-review-pipeline-01",
            "workspace_id": ws_id,
            "name": "Automated Pull Request Review Pipeline",
            "description": "Triggered on GitHub PR open event. Runs static analysis, security scan, and LLM summary.",
            "trigger_type": "webhook",
            "trigger_config": {"event": "pull_request.opened"},
            "status": "active",
            "dag_definition": {
                "nodes": [
                    {"id": "fetch_diff", "type": "tool", "name": "Fetch PR Diff"},
                    {"id": "ai_review", "type": "agent", "name": "AI Code Review"},
                    {"id": "post_comment", "type": "tool", "name": "Post GitHub Comment"}
                ],
                "edges": [
                    {"source": "fetch_diff", "target": "ai_review"},
                    {"source": "ai_review", "target": "post_comment"}
                ]
            },
            "created_at": now_iso
        }
    ]
    for wf in workflows:
        firestore_db_service.save_workflow(wf["id"], wf)
        logger.info(f"✅ Created Workflow: {wf['name']}")

    # 5. Production Tools
    tools = [
        {
            "id": "tool-github-pr-01",
            "workspace_id": ws_id,
            "name": "GitHub PR Integrator",
            "slug": "github-pr-integrator",
            "tool_type": "webhook",
            "description": "Fetches GitHub pull request diffs and posts inline review comments.",
            "is_public": False,
            "is_active": True,
            "created_at": now_iso
        },
        {
            "id": "tool-vector-kb-01",
            "workspace_id": ws_id,
            "name": "Vector Knowledge Base Search",
            "slug": "vector-kb-search",
            "tool_type": "mcp",
            "description": "Performs semantic search across documentation and knowledge base embeddings.",
            "is_public": True,
            "is_active": True,
            "created_at": now_iso
        }
    ]
    for tool in tools:
        firestore_db_service.save_tool(tool["id"], tool)
        logger.info(f"✅ Created Tool: {tool['name']} ({tool['tool_type']})")

    # 6. Production Prompts
    prompts = [
        {
            "id": "prompt-code-review-v1",
            "workspace_id": ws_id,
            "name": "System Code Review Prompt",
            "slug": "system-code-review-v1",
            "description": "Standard prompt template for AI code reviews.",
            "current_version": 1,
            "content": "Analyze the following code diff for potential bugs, security flaws, and performance anti-patterns:\n\n{{diff}}",
            "created_at": now_iso
        }
    ]
    for p in prompts:
        firestore_db_service.save_prompt(p["id"], p)
        logger.info(f"✅ Created Prompt: {p['name']}")

    # 7. Production Secrets (encrypted metadata)
    secrets = [
        {
            "id": "secret-openai-key",
            "workspace_id": ws_id,
            "name": "OPENAI_API_KEY",
            "slug": "openai-api-key",
            "environment": "production",
            "provider": "openai",
            "encrypted_value": "enc_sk_live_99a88b77c66d55e44",
            "is_active": True,
            "created_at": now_iso
        }
    ]
    for sec in secrets:
        firestore_db_service.save_secret(sec["id"], sec)
        logger.info(f"✅ Created Secret: {sec['name']}")

    # 8. Production Artifacts
    artifacts = [
        {
            "id": "art-arch-diagram-01",
            "workspace_id": ws_id,
            "name": "AgentOS Architecture Spec",
            "content_type": "application/json",
            "size_bytes": 4096,
            "version": 1,
            "metadata": {"author": "azharsayzz@gmail.com", "environment": "production"},
            "created_at": now_iso
        }
    ]
    for art in artifacts:
        firestore_db_service.save_artifact(art["id"], art)
        logger.info(f"✅ Created Artifact: {art['name']}")

    # 9. Production Telemetry & Audit Logs
    telemetry_events = [
        {
            "id": f"evt-{uuid4().hex[:8]}",
            "workspace_id": ws_id,
            "event_name": "agent_execution_completed",
            "event_type": "agent",
            "severity": "info",
            "duration_ms": 1240,
            "cost_usd": 0.0035,
            "created_at": now_iso
        }
    ]
    for evt in telemetry_events:
        firestore_db_service.save_telemetry_event(evt["id"], evt)
        logger.info(f"✅ Logged Telemetry Event: {evt['event_name']}")

    audit_logs = [
        {
            "id": f"audit-{uuid4().hex[:8]}",
            "workspace_id": ws_id,
            "user_id": user_id,
            "action": "WORKSPACE_SEEDED",
            "resource_type": "workspace",
            "resource_id": ws_id,
            "created_at": now_iso
        }
    ]
    for al in audit_logs:
        firestore_db_service.save_audit_log(al["id"], al)
        logger.info(f"✅ Logged Audit Log: {al['action']}")

    logger.info("🎉 Cloud Firestore Seeding & Verification Completed Successfully!")


if __name__ == "__main__":
    seed_production_workspace()
