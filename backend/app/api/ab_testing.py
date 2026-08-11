"""A/B Testing API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404
from app.core.db import FirestoreDB
from app.core.database import get_db
from app.services import ab_testing

router = APIRouter(prefix="/workspaces/{workspace_id}/ab-tests", tags=["ab-testing"])


# ─── Schemas ─────────────────────────────────────────

class ABTestCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = None
    prompt_id: str | None = None
    variants: list[dict] | None = None
    traffic_split: int = Field(50, ge=0, le=100)


class VariantUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    is_control: bool | None = None


class ABResultCreate(BaseModel):
    variant_id: str
    input: str
    output: str
    score: float | None = Field(None, ge=0.0, le=1.0)
    latency_ms: int | None = None
    tokens_used: int | None = None
    user_feedback: str | None = Field(None, pattern="^(positive|negative|neutral)$")


# ─── Tests ───────────────────────────────────────────

@router.get("")
async def list_tests(
    workspace_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """List all A/B tests for a workspace."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return ab_testing.list_ab_tests(db, workspace["id"])


@router.post("")
async def create_test(
    workspace_id: str,
    test_in: ABTestCreate,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Create a new A/B test."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return ab_testing.create_ab_test(
        db, workspace["id"],
        name=test_in.name,
        description=test_in.description,
        prompt_id=test_in.prompt_id,
        variants=test_in.variants,
    )


@router.get("/{test_id}")
async def get_test(
    workspace_id: str,
    test_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get an A/B test by ID."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    test = ab_testing.get_ab_test(db, test_id)
    if not test or test.get("workspace_id") != workspace["id"]:
        raise HTTPException(status_code=404, detail="Test not found")
    return test


@router.post("/{test_id}/start")
async def start_test(
    workspace_id: str,
    test_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Start an A/B test."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return ab_testing.start_ab_test(db, test_id)


@router.post("/{test_id}/stop")
async def stop_test(
    workspace_id: str,
    test_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Stop an A/B test."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return ab_testing.stop_ab_test(db, test_id)


@router.get("/{test_id}/results")
async def get_results(
    workspace_id: str,
    test_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get aggregated results for an A/B test."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return ab_testing.get_test_results(db, test_id)


@router.post("/{test_id}/results")
async def record_result(
    workspace_id: str,
    test_id: str,
    result_in: ABResultCreate,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Record a result for an A/B test variant."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return ab_testing.record_ab_result(
        db, test_id,
        variant_id=result_in.variant_id,
        input_text=result_in.input,
        output_text=result_in.output,
        score=result_in.score,
        latency_ms=result_in.latency_ms,
        tokens_used=result_in.tokens_used,
        user_feedback=result_in.user_feedback,
    )


# ─── Variants ────────────────────────────────────────

@router.get("/{test_id}/variants")
async def list_variants(
    workspace_id: str,
    test_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """List all variants for an A/B test."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return ab_testing.list_variants(db, test_id)


@router.patch("/{test_id}/variants/{variant_id}")
async def update_variant(
    workspace_id: str,
    test_id: str,
    variant_id: str,
    update_in: VariantUpdate,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Update a variant."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return ab_testing.update_variant(
        db, variant_id,
        update_in.model_dump(exclude_unset=True),
    )
