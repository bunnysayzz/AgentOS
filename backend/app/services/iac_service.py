"""Infrastructure as Code service — YAML export/import for agents, workflows, prompts."""

import json
from datetime import datetime, timezone
from app.core.db import FirestoreDB, now_iso

AGENTS = "agents"
WORKFLOWS = "workflows"
PROMPTS = "prompts"
TOOLS = "tools"
IAC_VERSION = "1.0"


def export_workspace_as_iac(db: FirestoreDB, workspace_id: str) -> dict:
    """Export all workspace resources as IaC manifest."""
    agents = [a for a in db.query(AGENTS, "workspace_id", workspace_id) if not a.get("deleted_at")]
    workflows = [w for w in db.query(WORKFLOWS, "workspace_id", workspace_id) if not w.get("deleted_at")]
    prompts = [p for p in db.query(PROMPTS, "workspace_id", workspace_id) if not p.get("deleted_at")]
    tools = [t for t in db.query(TOOLS, "workspace_id", workspace_id) if not t.get("deleted_at")]
    
    return {
        "agentos_version": IAC_VERSION,
        "exported_at": now_iso(),
        "workspace_id": workspace_id,
        "resources": {
            "agents": [_export_agent(a) for a in agents],
            "workflows": [_export_workflow(w) for w in workflows],
            "prompts": [_export_prompt(p) for p in prompts],
            "tools": [_export_tool(t) for t in tools],
        },
        "summary": {
            "agents": len(agents),
            "workflows": len(workflows),
            "prompts": len(prompts),
            "tools": len(tools),
        },
    }


def _export_agent(agent: dict) -> dict:
    """Export an agent as IaC-friendly dict."""
    return {
        "name": agent.get("name"),
        "description": agent.get("description"),
        "system_prompt": agent.get("system_prompt"),
        "model_name": agent.get("model_name"),
        "model_provider": agent.get("model_provider"),
        "temperature": agent.get("temperature", 0.7),
        "max_tokens": agent.get("max_tokens", 4096),
        "tool_refs": agent.get("tool_ids", []),
    }


def _export_workflow(workflow: dict) -> dict:
    """Export a workflow as IaC-friendly dict."""
    return {
        "name": workflow.get("name"),
        "description": workflow.get("description"),
        "trigger_type": workflow.get("trigger_type", "manual"),
        "schedule_cron": workflow.get("schedule_cron"),
        "dag_definition": workflow.get("dag_definition"),
    }


def _export_prompt(prompt: dict) -> dict:
    """Export a prompt as IaC-friendly dict."""
    return {
        "name": prompt.get("name"),
        "slug": prompt.get("slug"),
        "content": prompt.get("content"),
        "prompt_type": prompt.get("prompt_type", "system"),
        "variables": prompt.get("variables"),
        "version": prompt.get("version", 1),
    }


def _export_tool(tool: dict) -> dict:
    """Export a tool as IaC-friendly dict."""
    return {
        "name": tool.get("name"),
        "slug": tool.get("slug"),
        "description": tool.get("description"),
        "tool_type": tool.get("tool_type"),
        "config": tool.get("config"),
    }


def import_iac_to_workspace(
    db: FirestoreDB,
    workspace_id: str,
    manifest: dict,
    dry_run: bool = False,
) -> dict:
    """Import an IaC manifest into a workspace."""
    version = manifest.get("agentos_version", "1.0")
    if version != IAC_VERSION:
        return {"success": False, "error": f"Unsupported IaC version: {version}"}
    
    resources = manifest.get("resources", {})
    imported = {"agents": 0, "workflows": 0, "prompts": 0, "tools": 0}
    errors = []
    
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "would_import": {
                "agents": len(resources.get("agents", [])),
                "workflows": len(resources.get("workflows", [])),
                "prompts": len(resources.get("prompts", [])),
                "tools": len(resources.get("tools", [])),
            },
        }
    
    # Import tools first (agents may reference them)
    tool_id_map = {}
    for tool_data in resources.get("tools", []):
        try:
            tool = {
                "id": now_iso() + "-tool",
                "workspace_id": workspace_id,
                "name": tool_data.get("name"),
                "slug": tool_data.get("slug"),
                "description": tool_data.get("description"),
                "tool_type": tool_data.get("tool_type"),
                "config": tool_data.get("config"),
                "created_at": now_iso(),
            }
            db.add(TOOLS, tool)
            tool_id_map[tool_data.get("slug", "")] = tool["id"]
            imported["tools"] += 1
        except Exception as e:
            errors.append(f"Tool '{tool_data.get('name')}': {str(e)}")
    
    # Import prompts
    for prompt_data in resources.get("prompts", []):
        try:
            prompt = {
                "id": now_iso() + "-prompt",
                "workspace_id": workspace_id,
                "name": prompt_data.get("name"),
                "slug": prompt_data.get("slug"),
                "content": prompt_data.get("content"),
                "prompt_type": prompt_data.get("prompt_type", "system"),
                "variables": prompt_data.get("variables"),
                "version": prompt_data.get("version", 1),
                "created_at": now_iso(),
            }
            db.add(PROMPTS, prompt)
            imported["prompts"] += 1
        except Exception as e:
            errors.append(f"Prompt '{prompt_data.get('name')}': {str(e)}")
    
    # Import workflows
    for wf_data in resources.get("workflows", []):
        try:
            workflow = {
                "id": now_iso() + "-wf",
                "workspace_id": workspace_id,
                "name": wf_data.get("name"),
                "description": wf_data.get("description"),
                "trigger_type": wf_data.get("trigger_type", "manual"),
                "schedule_cron": wf_data.get("schedule_cron"),
                "dag_definition": wf_data.get("dag_definition"),
                "status": "active",
                "created_at": now_iso(),
            }
            db.add(WORKFLOWS, workflow)
            imported["workflows"] += 1
        except Exception as e:
            errors.append(f"Workflow '{wf_data.get('name')}': {str(e)}")
    
    # Import agents (resolve tool refs)
    for agent_data in resources.get("agents", []):
        try:
            tool_refs = agent_data.get("tool_refs", [])
            resolved_tools = [tool_id_map.get(ref, ref) for ref in tool_refs]
            
            agent = {
                "id": now_iso() + "-agent",
                "workspace_id": workspace_id,
                "name": agent_data.get("name"),
                "description": agent_data.get("description"),
                "system_prompt": agent_data.get("system_prompt"),
                "model_name": agent_data.get("model_name"),
                "model_provider": agent_data.get("model_provider"),
                "temperature": agent_data.get("temperature", 0.7),
                "max_tokens": agent_data.get("max_tokens", 4096),
                "tool_ids": resolved_tools,
                "status": "active",
                "created_at": now_iso(),
            }
            db.add(AGENTS, agent)
            imported["agents"] += 1
        except Exception as e:
            errors.append(f"Agent '{agent_data.get('name')}': {str(e)}")
    
    return {
        "success": len(errors) == 0,
        "imported": imported,
        "errors": errors,
    }
