"""Evaluation framework API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404
from app.core.db import FirestoreDB
from app.core.database import get_db
from app.services import eval_service

router = APIRouter(prefix="/workspaces/{workspace_id}/evaluations", tags=["evaluations"])


# ─── Schemas ─────────────────────────────────────────

class EvalSuiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = None
    test_cases: list[dict] | None = None


class TestCaseCreate(BaseModel):
    input: str = Field(..., min_length=1)
    expected_output: str | None = None
    criteria: str | None = None
    tags: list[str] | None = None


class EvalRunCreate(BaseModel):
    suite_id: str
    agent_id: str | None = None
    model_name: str | None = None


class EvalResultCreate(BaseModel):
    test_case_id: str
    input: str
    actual_output: str
    score: float = Field(ge=0.0, le=1.0)
    judge_reasoning: str | None = None
    passed: bool | None = None


# ─── Suites ──────────────────────────────────────────

@router.get("/suites")
async def list_suites(
    workspace_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """List all evaluation suites for a workspace."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return eval_service.list_eval_suites(db, workspace["id"])


@router.post("/suites")
async def create_suite(
    workspace_id: str,
    suite_in: EvalSuiteCreate,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Create a new evaluation suite."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return eval_service.create_eval_suite(
        db, workspace["id"],
        name=suite_in.name,
        description=suite_in.description,
        test_cases=suite_in.test_cases,
    )


@router.get("/suites/{suite_id}")
async def get_suite(
    workspace_id: str,
    suite_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get an evaluation suite by ID."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    suite = eval_service.get_eval_suite(db, suite_id)
    if not suite or suite.get("workspace_id") != workspace["id"]:
        raise HTTPException(status_code=404, detail="Suite not found")
    return suite


@router.post("/suites/{suite_id}/test-cases")
async def add_test_case(
    workspace_id: str,
    suite_id: str,
    tc_in: TestCaseCreate,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Add a test case to an eval suite."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return eval_service.add_test_case(
        db, suite_id,
        input_text=tc_in.input,
        expected_output=tc_in.expected_output,
        criteria=tc_in.criteria,
        tags=tc_in.tags,
    )


# ─── Runs ────────────────────────────────────────────

@router.get("/runs")
async def list_runs(
    workspace_id: str,
    suite_id: str | None = None,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """List evaluation runs."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return eval_service.list_eval_runs(db, workspace["id"], suite_id)


@router.post("/runs")
async def create_run(
    workspace_id: str,
    run_in: EvalRunCreate,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Create a new evaluation run."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return eval_service.create_eval_run(
        db, workspace["id"],
        suite_id=run_in.suite_id,
        agent_id=run_in.agent_id,
        model_name=run_in.model_name,
    )


@router.get("/runs/{run_id}")
async def get_run(
    workspace_id: str,
    run_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get an eval run by ID."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    run = eval_service.get_eval_run(db, run_id)
    if not run or run.get("workspace_id") != workspace["id"]:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/runs/{run_id}/results")
async def record_result(
    workspace_id: str,
    run_id: str,
    result_in: EvalResultCreate,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Record an eval result for a run."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return eval_service.record_eval_result(
        db, run_id,
        test_case_id=result_in.test_case_id,
        input_text=result_in.input,
        actual_output=result_in.actual_output,
        score=result_in.score,
        judge_reasoning=result_in.judge_reasoning,
        passed=result_in.passed,
    )


@router.post("/runs/{run_id}/complete")
async def complete_run(
    workspace_id: str,
    run_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Mark an eval run as completed and compute summary."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return eval_service.complete_eval_run(db, run_id)


@router.post("/runs/{run_id}/execute")
async def execute_run(
    workspace_id: str,
    run_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Auto-execute every test case in a run and judge the outputs."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    run = eval_service.get_eval_run(db, run_id)
    if not run or run.get("workspace_id") != workspace["id"]:
        raise HTTPException(status_code=404, detail="Run not found")
    return await eval_service.execute_eval_run(db, run_id)


@router.get("/runs/{run_id}/regression")
async def check_regression(
    workspace_id: str,
    run_id: str,
    threshold: float = Query(0.1, ge=0.0, le=1.0),
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Check if current run regresses against previous runs."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    run = eval_service.get_eval_run(db, run_id)
    if not run or run.get("workspace_id") != workspace["id"]:
        raise HTTPException(status_code=404, detail="Run not found")
    return eval_service.detect_regression(
        db, workspace["id"], run["suite_id"], run_id, threshold
    )
