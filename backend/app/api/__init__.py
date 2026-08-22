"""API router - aggregates all domain routers."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.workspaces import router as workspaces_router
from app.api.agents import router as agents_router, templates_router
from app.api.tools import router as tools_router
from app.api.mcp import router as mcp_router
from app.api.prompts import router as prompts_router
from app.api.workflows import router as workflows_router
from app.api.memory import router as memory_router
from app.api.secrets import router as secrets_router
from app.api.artifacts import router as artifacts_router
from app.api.execution_graphs import router as execution_graphs_router
from app.api.telemetry import router as telemetry_router
from app.api.provider_configs import router as provider_configs_router
from app.api.api_keys import router as api_keys_router
from app.api.gallery import router as gallery_router
from app.api.webhooks import router as webhooks_router
from app.api.dashboard import router as dashboard_router
from app.api.demo import router as demo_router
from app.api.budgets import router as budgets_router
from app.api.webhook_debugger import router as webhook_debugger_router
from app.api.evaluations import router as evaluations_router
from app.api.iac import router as iac_router
from app.api.ab_testing import router as ab_testing_router
from app.api.team import router as team_router

router = APIRouter()

# Include sub-routers
router.include_router(auth_router)
router.include_router(api_keys_router)
router.include_router(gallery_router)
router.include_router(users_router)
router.include_router(workspaces_router)
router.include_router(agents_router)
router.include_router(templates_router)
router.include_router(tools_router)
router.include_router(mcp_router)
router.include_router(provider_configs_router)
router.include_router(prompts_router)
router.include_router(workflows_router)
router.include_router(memory_router)
router.include_router(secrets_router)
router.include_router(artifacts_router)
router.include_router(execution_graphs_router)
router.include_router(telemetry_router)
router.include_router(webhooks_router)
router.include_router(dashboard_router)
router.include_router(demo_router)
router.include_router(budgets_router)
router.include_router(webhook_debugger_router)
router.include_router(evaluations_router)
router.include_router(iac_router)
router.include_router(ab_testing_router)
router.include_router(team_router)


@router.get("/")
async def root():
    """API root - returns service information."""
    return {
        "service": "AgentOS Studio API",
        "version": "0.1.0",
        "docs": "/docs",
    }
