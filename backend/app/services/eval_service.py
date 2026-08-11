"""Evaluation framework service — LLM judges, regression detection, eval runs."""

import json
from datetime import datetime, timezone
from app.core.db import FirestoreDB, new_id, now_iso

EVAL_SUITES = "eval_suites"
EVAL_RUNS = "eval_runs"
EVAL_RESULTS = "eval_results"


# ─── Eval Suites ─────────────────────────────────────

def create_eval_suite(
    db: FirestoreDB,
    workspace_id: str,
    name: str,
    description: str | None = None,
    test_cases: list[dict] | None = None,
) -> dict:
    """Create an evaluation suite with test cases."""
    suite = {
        "id": new_id(),
        "workspace_id": workspace_id,
        "name": name,
        "description": description,
        "test_cases": test_cases or [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    db.add(EVAL_SUITES, suite)
    return suite


def list_eval_suites(db: FirestoreDB, workspace_id: str) -> list[dict]:
    """List all eval suites for a workspace."""
    rows = db.query(EVAL_SUITES, "workspace_id", workspace_id)
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def get_eval_suite(db: FirestoreDB, suite_id: str) -> dict | None:
    """Get an eval suite by ID."""
    return db.get(EVAL_SUITES, suite_id)


def add_test_case(
    db: FirestoreDB,
    suite_id: str,
    input_text: str,
    expected_output: str | None = None,
    criteria: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Add a test case to an eval suite."""
    suite = db.get(EVAL_SUITES, suite_id)
    if not suite:
        from app.services.workspace_service import WorkspaceNotFoundError
        raise WorkspaceNotFoundError()
    
    test_case = {
        "id": new_id(),
        "input": input_text,
        "expected_output": expected_output,
        "criteria": criteria,
        "tags": tags or [],
        "created_at": now_iso(),
    }
    
    test_cases = suite.get("test_cases") or []
    test_cases.append(test_case)
    suite["test_cases"] = test_cases
    suite["updated_at"] = now_iso()
    db.set(EVAL_SUITES, suite_id, suite)
    return test_case


# ─── Eval Runs ───────────────────────────────────────

def create_eval_run(
    db: FirestoreDB,
    workspace_id: str,
    suite_id: str,
    agent_id: str | None = None,
    model_name: str | None = None,
) -> dict:
    """Create an evaluation run."""
    run = {
        "id": new_id(),
        "workspace_id": workspace_id,
        "suite_id": suite_id,
        "agent_id": agent_id,
        "model_name": model_name,
        "status": "pending",
        "results": [],
        "summary": None,
        "created_at": now_iso(),
        "completed_at": None,
    }
    db.add(EVAL_RUNS, run)
    return run


def list_eval_runs(db: FirestoreDB, workspace_id: str, suite_id: str | None = None) -> list[dict]:
    """List eval runs for a workspace."""
    if suite_id:
        rows = db.query(EVAL_RUNS, "suite_id", suite_id)
    else:
        rows = db.query(EVAL_RUNS, "workspace_id", workspace_id)
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def get_eval_run(db: FirestoreDB, run_id: str) -> dict | None:
    """Get an eval run by ID."""
    return db.get(EVAL_RUNS, run_id)


def record_eval_result(
    db: FirestoreDB,
    run_id: str,
    test_case_id: str,
    input_text: str,
    actual_output: str,
    score: float,  # 0.0 - 1.0
    judge_reasoning: str | None = None,
    passed: bool | None = None,
) -> dict:
    """Record a single eval result."""
    run = db.get(EVAL_RUNS, run_id)
    if not run:
        from app.services.workspace_service import WorkspaceNotFoundError
        raise WorkspaceNotFoundError()
    
    result = {
        "id": new_id(),
        "run_id": run_id,
        "test_case_id": test_case_id,
        "input": input_text,
        "actual_output": actual_output,
        "score": score,
        "judge_reasoning": judge_reasoning,
        "passed": passed if passed is not None else score >= 0.7,
        "created_at": now_iso(),
    }
    
    results = run.get("results") or []
    results.append(result)
    run["results"] = results
    db.set(EVAL_RUNS, run_id, run)
    return result


def complete_eval_run(db: FirestoreDB, run_id: str) -> dict:
    """Mark an eval run as completed and compute summary."""
    run = db.get(EVAL_RUNS, run_id)
    if not run:
        from app.services.workspace_service import WorkspaceNotFoundError
        raise WorkspaceNotFoundError()
    
    results = run.get("results") or []
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    scores = [r.get("score", 0) for r in results]
    avg_score = sum(scores) / total if total > 0 else 0
    
    run["status"] = "completed"
    run["completed_at"] = now_iso()
    run["summary"] = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
        "avg_score": round(avg_score, 3),
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
    }
    db.set(EVAL_RUNS, run_id, run)
    return run


def detect_regression(
    db: FirestoreDB,
    workspace_id: str,
    suite_id: str,
    current_run_id: str,
    threshold: float = 0.1,
) -> dict:
    """Compare current run against previous runs to detect regressions."""
    runs = list_eval_runs(db, workspace_id, suite_id)
    completed = [r for r in runs if r.get("status") == "completed" and r["id"] != current_run_id]
    
    if not completed:
        return {"regression_detected": False, "message": "No previous runs to compare against"}
    
    current = db.get(EVAL_RUNS, current_run_id)
    if not current or current.get("status") != "completed":
        return {"regression_detected": False, "message": "Current run not completed yet"}
    
    current_summary = current.get("summary") or {}
    previous_summary = completed[0].get("summary") or {}
    
    current_rate = current_summary.get("pass_rate", 0)
    previous_rate = previous_summary.get("pass_rate", 0)
    
    regression = previous_rate - current_rate > threshold * 100
    
    return {
        "regression_detected": regression,
        "current_pass_rate": current_rate,
        "previous_pass_rate": previous_rate,
        "threshold": threshold * 100,
        "message": f"Pass rate dropped from {previous_rate}% to {current_rate}%" if regression else "No regression detected",
    }
