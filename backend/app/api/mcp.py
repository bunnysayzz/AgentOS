"""MCP Gateway API routes - LLM chat, model registry, cost governance."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_active_user, get_optional_user
from app.api.workspaces import get_workspace_or_404, require_workspace_role
from app.schemas.mcp import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelInfo,
    ModelListResponse,
    CostSummary,
    CostByProvider,
    CostByModel,
    CostDashboardResponse,
)
from app.models.user import User
from app.models.workspace import Workspace, MembershipRole
from app.models.mcp import LLMProvider
from app.services import mcp_service

router = APIRouter(tags=["MCP Gateway"])


# ─── Chat/Completion ────────────────────────────────


@router.post("/mcp/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    workspace_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """Send a chat completion request to an LLM model.
    
    If workspace_id is provided, the call is scoped to that workspace
    and the user must have access.
    """
    # Verify workspace access if specified
    if workspace_id:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for workspace-scoped chat",
            )
        from app.services import workspace_service
        membership = await workspace_service.get_workspace_membership(
            db, current_user.id, workspace_id
        )
        if membership is None and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to workspace")

    response = await mcp_service.route_chat_completion(
        db=db,
        request=request,
        workspace_id=workspace_id,
    )
    return response


# ─── Models ─────────────────────────────────────────


@router.get("/mcp/models", response_model=ModelListResponse)
async def list_models(
    provider: LLMProvider | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all available LLM models with pricing and capabilities."""
    models = await mcp_service.get_available_models(db, provider=provider)
    model_infos = [
        ModelInfo(
            id=f"{m.provider}/{m.model_name}",
            provider=m.provider,
            model_name=m.model_name,
            capabilities=m.capabilities if m.capabilities else [],
            input_price_per_1k=m.input_price_per_1k,
            output_price_per_1k=m.output_price_per_1k,
            context_window=m.context_window,
            max_output_tokens=m.max_output_tokens,
            is_active=m.is_active,
            description=m.description,
        )
        for m in models
    ]
    # Fall back to hardcoded defaults if DB is empty
    if not model_infos:
        for model_name, pricing in mcp_service.DEFAULT_MODEL_PRICING.items():
            provider_name = LLMProvider.OPENAI
            if model_name.startswith("claude"):
                provider_name = LLMProvider.ANTHROPIC
            elif model_name.startswith("gemini"):
                provider_name = LLMProvider.GOOGLE
            model_infos.append(
                ModelInfo(
                    id=f"{provider_name.value}/{model_name}",
                    provider=provider_name,
                    model_name=model_name,
                    capabilities=["chat", "function_calling", "streaming"],
                    input_price_per_1k=pricing["input"],
                    output_price_per_1k=pricing["output"],
                    context_window=pricing["context"],
                    max_output_tokens=8192,
                    is_active=True,
                    description=None,
                )
            )

    return ModelListResponse(models=model_infos, total=len(model_infos))


@router.post("/mcp/models/seed", status_code=status.HTTP_200_OK)
async def seed_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Seed default model pricing into the registry (idempotent)."""
    count = await mcp_service.seed_default_models(db)
    return {"seeded": count, "message": f"Seeded {count} default models (0 if already seeded)"}


# ─── Cost Dashboard ─────────────────────────────────


@router.get("/mcp/costs", response_model=CostDashboardResponse)
async def get_cost_dashboard(
    workspace_id: UUID | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """Get LLM cost dashboard with breakdowns by provider and model."""
    summary = await mcp_service.get_cost_summary(db, workspace_id=workspace_id, days=days)
    by_provider = await mcp_service.get_cost_by_provider(db, workspace_id=workspace_id, days=days)
    by_model = await mcp_service.get_cost_by_model(db, workspace_id=workspace_id, days=days)

    return CostDashboardResponse(
        summary=CostSummary(**summary),
        by_provider=[CostByProvider(**p) for p in by_provider],
        by_model=[CostByModel(**m) for m in by_model],
    )


@router.get("/mcp/calls", response_model=list[dict])
async def list_recent_calls(
    workspace_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """List recent LLM calls for observability."""
    calls = await mcp_service.get_recent_calls(db, workspace_id=workspace_id, limit=limit)
    return [
        {
            "id": str(c.id),
            "provider": c.provider,
            "model": c.model_name,
            "tokens": c.total_tokens,
            "cost_usd": c.cost_usd,
            "duration_ms": c.duration_ms,
            "is_error": c.is_error,
            "created_at": c.created_at,
        }
        for c in calls
    ]
