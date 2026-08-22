"""Evaluation framework service — LLM judges, regression detection, eval runs."""

import difflib
import json

from app.core.db import FirestoreDB, new_id, now_iso

EVAL_SUITES = "eval_suites"
EVAL_RUNS = "eval_runs"
EVAL_RESULTS = "eval_results"

_JUDGE_PROMPT = """You are an evaluation judge. Score how well the assistant's response answers the input.

Input:
{input_text}

Expected output:
{expected}

Evaluation criteria:
{criteria}

Assistant response:
{actual}

Reply with JSON only, no markdown, in exactly this shape:
{{"score": <number 0.0 to 1.0>, "passed": <true or false>, "reasoning": "<one or two sentences>"}}"""


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

    run["status"] = "completed"
    run["completed_at"] = now_iso()
    run["summary"] = _build_summary(run.get("results") or [])
    db.set(EVAL_RUNS, run_id, run)
    return run


def _build_summary(results: list[dict]) -> dict:
    """Aggregate eval results into the run summary shape."""
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    scores = [r.get("score", 0) for r in results]
    avg_score = sum(scores) / total if total > 0 else 0
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
        "avg_score": round(avg_score, 3),
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
    }


# ─── Auto-execution (run the agent, then LLM-judge) ──


async def execute_eval_run(db: FirestoreDB, run_id: str) -> dict:
    """Execute every test case in a run's suite and judge the outputs.

    Each case runs through the run's agent (full tool loop via the execution
    engine) or the run's bare model, then an LLM judge scores it. If the judge
    is unreachable or returns unparseable JSON, a deterministic heuristic
    scores the case instead. The run ends ``completed`` with the same summary
    shape as a manually-recorded run.
    """
    from app.services.workspace_service import WorkspaceNotFoundError

    run = db.get(EVAL_RUNS, run_id)
    if not run:
        raise WorkspaceNotFoundError()
    if run.get("status") == "completed":
        return run

    suite = db.get(EVAL_SUITES, run.get("suite_id") or "")
    if not suite:
        raise WorkspaceNotFoundError()

    run["status"] = "running"
    run["started_at"] = now_iso()
    run["error_message"] = None
    db.set(EVAL_RUNS, run_id, run)

    results: list[dict] = []
    for tc in suite.get("test_cases") or []:
        result = {
            "id": new_id(),
            "run_id": run_id,
            "test_case_id": tc.get("id"),
            "input": tc.get("input", ""),
            "actual_output": "",
            "score": 0.0,
            "passed": False,
            "judge_reasoning": "",
            "created_at": now_iso(),
        }
        try:
            actual = await _execute_case(db, run, tc)
            if _is_all_providers_error(actual):
                raise RuntimeError("No LLM provider available to run this evaluation")
            result["actual_output"] = actual
            if not actual.strip():
                result["judge_reasoning"] = "Agent produced no output"
            else:
                result.update(await _judge_case(db, run, tc, actual))
        except Exception as exc:
            result["judge_reasoning"] = f"Execution failed: {exc}"
            result["score"] = 0.0
            result["passed"] = False
        results.append(result)

    run["results"] = results
    run["status"] = "completed"
    run["completed_at"] = now_iso()
    run["summary"] = _build_summary(results)
    db.set(EVAL_RUNS, run_id, run)
    return run


async def _execute_case(db: FirestoreDB, run: dict, tc: dict) -> str:
    """Run one test case through the run's agent or model; return the output."""
    from app.schemas.agent import AgentExecutionCreate
    from app.schemas.mcp import ChatCompletionRequest, ChatMessage
    from app.services import agent_service, execution_engine, mcp_service

    agent_id = run.get("agent_id")
    if agent_id:
        agent = await agent_service.get_agent_by_id(db, agent_id)
        if agent is None:
            raise RuntimeError("Agent not found")
        execution = await agent_service.create_execution(
            db,
            agent_id,
            AgentExecutionCreate(input_data={"input": tc.get("input", "")}),
        )
        await agent_service.start_execution(db, execution)
        await execution_engine.run_agent_execution(db, execution["id"])
        finished = await agent_service.get_execution_by_id(db, execution["id"])
        if not finished or finished.get("status") != "completed":
            raise RuntimeError(finished.get("error_message") or "Agent execution failed")
        return str((finished.get("output_data") or {}).get("response") or "")

    response = await mcp_service.route_chat_completion(
        db,
        ChatCompletionRequest(
            model=run.get("model_name") or "gpt-4o",
            messages=[ChatMessage(role="user", content=tc.get("input", ""))],
        ),
        workspace_id=run.get("workspace_id"),
    )
    return response.choices[0]["message"]["content"] if response.choices else ""


async def _judge_case(db: FirestoreDB, run: dict, tc: dict, actual: str) -> dict:
    """Score an output with an LLM judge, falling back to heuristics."""
    try:
        verdict = await _llm_judge(
            db, run.get("workspace_id"), run.get("model_name") or "gpt-4o", tc, actual
        )
        if verdict:
            return verdict
    except Exception:
        pass
    return _heuristic_judge(tc, actual)


async def _llm_judge(
    db: FirestoreDB,
    workspace_id: str | None,
    model_name: str,
    tc: dict,
    actual: str,
) -> dict | None:
    """Ask the LLM to score a case; returns None if the verdict can't be parsed."""
    from app.schemas.mcp import ChatCompletionRequest, ChatMessage
    from app.services import mcp_service

    prompt = _JUDGE_PROMPT.format(
        input_text=tc.get("input", ""),
        expected=(tc.get("expected_output") or "(none)").strip(),
        criteria=(tc.get("criteria") or "(none)").strip(),
        actual=actual[:8000],
    )
    response = await mcp_service.route_chat_completion(
        db,
        ChatCompletionRequest(model=model_name, messages=[ChatMessage(role="user", content=prompt)]),
        workspace_id=workspace_id,
    )
    content = response.choices[0]["message"]["content"] if response.choices else ""
    parsed = _parse_judge_json(content)
    if parsed is None:
        return None
    score = max(0.0, min(1.0, float(parsed.get("score", 0.0))))
    return {
        "score": score,
        "passed": bool(parsed.get("passed", score >= 0.7)),
        "judge_reasoning": str(parsed.get("reasoning") or "")[:1000],
    }


def _parse_judge_json(content: str) -> dict | None:
    """Extract the JSON object from a judge response, tolerating prose."""
    if not content:
        return None
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(content[start : end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict) or "score" not in data:
        return None
    return data


def _heuristic_judge(tc: dict, actual: str) -> dict:
    """Deterministic fallback when no LLM judge is reachable."""
    actual_norm = (actual or "").strip().lower()
    expected = (tc.get("expected_output") or "").strip().lower()
    if expected and actual_norm:
        score = 1.0 if expected in actual_norm else round(
            difflib.SequenceMatcher(None, expected, actual_norm).ratio(), 3
        )
    else:
        score = 1.0 if actual_norm else 0.0
    return {
        "score": score,
        "passed": score >= 0.7,
        "judge_reasoning": "Heuristic score (LLM judge unavailable)",
    }


def _is_all_providers_error(content: str) -> bool:
    """Detect the MCP gateway's 'all providers unavailable' sentinel."""
    return bool(content) and content.startswith("\u26a0\ufe0f All providers unavailable")


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
