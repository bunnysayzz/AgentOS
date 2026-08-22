"""Tests for the Evaluation framework, A/B testing, and Infrastructure as Code APIs."""

import pytest
from httpx import AsyncClient


# ─── Helpers ─────────────────────────────────────────


async def _create_suite(client, headers, ws_id, name="Quality Suite"):
    resp = await client.post(
        f"/api/v1/workspaces/{ws_id}/evaluations/suites",
        json={"name": name, "description": "Measures output quality"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _create_ab_test(client, headers, ws_id, name="Prompt v2 test"):
    resp = await client.post(
        f"/api/v1/workspaces/{ws_id}/ab-tests",
        json={
            "name": name,
            "description": "Compare onboarding prompts",
            "variants": [
                {"name": "Control", "content": "You are helpful."},
                {"name": "Variant B", "content": "You are concise."},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ─── Evaluations ─────────────────────────────────────


class TestEvalSuites:
    async def test_create_and_list_suites(self, client, auth_headers, test_workspace):
        suite = await _create_suite(client, auth_headers, test_workspace["id"])
        assert suite["name"] == "Quality Suite"
        assert suite["test_cases"] == []

        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/evaluations/suites",
            headers=auth_headers,
        )
        assert listing.status_code == 200
        assert len(listing.json()) == 1

    async def test_suite_is_workspace_scoped(self, client, auth_headers, second_user, test_workspace):
        suite = await _create_suite(client, auth_headers, test_workspace["id"])
        other_ws = await client.post(
            "/api/v1/workspaces/", json={"name": "Other WS"}, headers=second_user["auth_headers"]
        )
        resp = await client.get(
            f"/api/v1/workspaces/{other_ws.json()['id']}/evaluations/suites/{suite['id']}",
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 404

    async def test_add_test_case(self, client, auth_headers, test_workspace):
        suite = await _create_suite(client, auth_headers, test_workspace["id"])
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/evaluations/suites/{suite['id']}/test-cases",
            json={
                "input": "Refund policy question",
                "expected_output": "Mentions 30-day window",
                "criteria": "Contains refund window",
                "tags": ["support"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["tags"] == ["support"]

        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/evaluations/suites",
            headers=auth_headers,
        )
        assert len(listing.json()[0]["test_cases"]) == 1


class TestEvalRuns:
    async def test_run_lifecycle_with_summary(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        suite = await _create_suite(client, auth_headers, ws)

        run = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs",
            json={"suite_id": suite["id"], "model_name": "gpt-4o"},
            headers=auth_headers,
        )
        assert run.status_code == 200, run.text
        run_id = run.json()["id"]
        assert run.json()["status"] == "pending"

        for score, passed in [(0.9, True), (0.4, False), (0.8, True)]:
            resp = await client.post(
                f"/api/v1/workspaces/{ws}/evaluations/runs/{run_id}/results",
                json={
                    "test_case_id": "tc-1",
                    "input": f"case {score}",
                    "actual_output": "agent reply",
                    "score": score,
                    "passed": passed,
                },
                headers=auth_headers,
            )
            assert resp.status_code == 200, resp.text

        completed = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs/{run_id}/complete",
            headers=auth_headers,
        )
        assert completed.status_code == 200
        data = completed.json()
        assert data["status"] == "completed"
        assert data["summary"]["total"] == 3
        assert data["summary"]["passed"] == 2
        assert data["summary"]["pass_rate"] == 66.7
        assert data["summary"]["avg_score"] == 0.7

    async def test_runs_filtered_by_suite(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        suite_a = await _create_suite(client, auth_headers, ws, name="A")
        suite_b = await _create_suite(client, auth_headers, ws, name="B")
        for suite in (suite_a, suite_b):
            await client.post(
                f"/api/v1/workspaces/{ws}/evaluations/runs",
                json={"suite_id": suite["id"]},
                headers=auth_headers,
            )
        listing = await client.get(
            f"/api/v1/workspaces/{ws}/evaluations/runs",
            params={"suite_id": suite_a["id"]},
            headers=auth_headers,
        )
        assert len(listing.json()) == 1
        assert listing.json()[0]["suite_id"] == suite_a["id"]


class TestRegression:
    async def _completed_run(self, client, headers, ws, suite_id, scores):
        run = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs",
            json={"suite_id": suite_id},
            headers=headers,
        )
        run_id = run.json()["id"]
        for i, score in enumerate(scores):
            await client.post(
                f"/api/v1/workspaces/{ws}/evaluations/runs/{run_id}/results",
                json={
                    "test_case_id": f"tc-{i}",
                    "input": f"case {i}",
                    "actual_output": "out",
                    "score": score,
                },
                headers=headers,
            )
        await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs/{run_id}/complete",
            headers=headers,
        )
        return run_id

    async def test_no_previous_runs_no_regression(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        suite = await _create_suite(client, auth_headers, ws)
        run_id = await self._completed_run(client, auth_headers, ws, suite["id"], [0.9, 0.8])

        resp = await client.get(
            f"/api/v1/workspaces/{ws}/evaluations/runs/{run_id}/regression",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["regression_detected"] is False

    async def test_drop_in_pass_rate_detected(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        suite = await _create_suite(client, auth_headers, ws)
        await self._completed_run(client, auth_headers, ws, suite["id"], [0.9, 0.9, 0.9, 0.9])
        run_id = await self._completed_run(client, auth_headers, ws, suite["id"], [0.9, 0.2, 0.3, 0.1])

        resp = await client.get(
            f"/api/v1/workspaces/{ws}/evaluations/runs/{run_id}/regression",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["regression_detected"] is True
        assert data["current_pass_rate"] == 25.0
        assert data["previous_pass_rate"] == 100.0

    async def test_uncompleted_run_reports_no_regression(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        suite = await _create_suite(client, auth_headers, ws)
        run = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs",
            json={"suite_id": suite["id"]},
            headers=auth_headers,
        )
        resp = await client.get(
            f"/api/v1/workspaces/{ws}/evaluations/runs/{run.json()['id']}/regression",
            headers=auth_headers,
        )
        assert resp.json()["regression_detected"] is False


# ─── A/B Testing ─────────────────────────────────────


class TestABTesting:
    async def test_create_and_list(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        test = await _create_ab_test(client, auth_headers, ws)
        assert test["status"] == "draft"
        assert test["traffic_split"] == 50

        variants = await client.get(
            f"/api/v1/workspaces/{ws}/ab-tests/{test['id']}/variants",
            headers=auth_headers,
        )
        assert variants.status_code == 200
        names = [v["name"] for v in variants.json()]
        assert names == ["Control", "Variant B"]
        assert variants.json()[0]["is_control"] is True

        listing = await client.get(f"/api/v1/workspaces/{ws}/ab-tests", headers=auth_headers)
        assert len(listing.json()) == 1

    async def test_start_stop_lifecycle(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        test = await _create_ab_test(client, auth_headers, ws)
        tid = test["id"]

        started = await client.post(
            f"/api/v1/workspaces/{ws}/ab-tests/{tid}/start", headers=auth_headers
        )
        assert started.status_code == 200
        assert started.json()["status"] == "running"
        assert started.json()["started_at"] is not None

        stopped = await client.post(
            f"/api/v1/workspaces/{ws}/ab-tests/{tid}/stop", headers=auth_headers
        )
        assert stopped.json()["status"] == "completed"

    async def test_results_aggregation_and_winner(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        test = await _create_ab_test(client, auth_headers, ws)
        tid = test["id"]
        variants = (
            await client.get(f"/api/v1/workspaces/{ws}/ab-tests/{tid}/variants", headers=auth_headers)
        ).json()
        control, variant_b = variants[0]["id"], variants[1]["id"]

        # 10 strong runs for control, 10 weak for variant B -> control wins
        for i in range(10):
            await client.post(
                f"/api/v1/workspaces/{ws}/ab-tests/{tid}/results",
                json={
                    "variant_id": control,
                    "input": f"q{i}",
                    "output": "out",
                    "score": 0.9,
                    "latency_ms": 100,
                    "tokens_used": 50,
                    "user_feedback": "positive",
                },
                headers=auth_headers,
            )
            await client.post(
                f"/api/v1/workspaces/{ws}/ab-tests/{tid}/results",
                json={
                    "variant_id": variant_b,
                    "input": f"q{i}",
                    "output": "out",
                    "score": 0.4,
                    "latency_ms": 300,
                    "tokens_used": 200,
                    "user_feedback": "negative",
                },
                headers=auth_headers,
            )

        results = await client.get(
            f"/api/v1/workspaces/{ws}/ab-tests/{tid}/results", headers=auth_headers
        )
        assert results.status_code == 200
        data = results.json()
        assert data["winner"] == control

        ctrl = data["variants"][control]
        assert ctrl["total_runs"] == 10
        assert ctrl["avg_score"] == 0.9
        assert ctrl["avg_latency_ms"] == 100
        assert ctrl["avg_tokens"] == 50
        assert ctrl["positive_feedback"] == 10
        assert ctrl["negative_feedback"] == 0

        var_b = data["variants"][variant_b]
        assert var_b["total_runs"] == 10
        assert var_b["avg_score"] == 0.4
        assert var_b["negative_feedback"] == 10

    async def test_no_winner_below_sample_size(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        test = await _create_ab_test(client, auth_headers, ws)
        tid = test["id"]
        variants = (
            await client.get(f"/api/v1/workspaces/{ws}/ab-tests/{tid}/variants", headers=auth_headers)
        ).json()
        await client.post(
            f"/api/v1/workspaces/{ws}/ab-tests/{tid}/results",
            json={"variant_id": variants[0]["id"], "input": "q", "output": "out", "score": 0.9},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/workspaces/{ws}/ab-tests/{tid}/results",
            json={"variant_id": variants[1]["id"], "input": "q", "output": "out", "score": 0.1},
            headers=auth_headers,
        )
        data = (
            await client.get(f"/api/v1/workspaces/{ws}/ab-tests/{tid}/results", headers=auth_headers)
        ).json()
        assert "winner" not in data or data["winner"] is None


# ─── Infrastructure as Code ──────────────────────────


class TestIaC:
    async def test_export_empty_workspace(self, client, auth_headers, test_workspace):
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/iac/export/json", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agentos_version"] == "1.0"
        assert data["summary"] == {"agents": 0, "workflows": 0, "prompts": 0, "tools": 0}

    async def test_export_includes_created_resources(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        await client.post(
            f"/api/v1/workspaces/{ws}/agents/",
            json={"name": "Exported Agent", "model_name": "gpt-4o", "system_prompt": "Be brief."},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/workspaces/{ws}/tools/",
            json={"name": "Exported Tool", "slug": "exported-tool", "description": "A tool"},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/workspaces/{ws}/prompts/",
            json={"name": "Exported Prompt", "slug": "exported-prompt"},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/workspaces/{ws}/workflows/",
            json={"name": "Exported Workflow"},
            headers=auth_headers,
        )

        data = (
            await client.get(f"/api/v1/workspaces/{ws}/iac/export/json", headers=auth_headers)
        ).json()
        assert data["summary"] == {"agents": 1, "workflows": 1, "prompts": 1, "tools": 1}
        assert data["resources"]["agents"][0]["name"] == "Exported Agent"
        assert data["resources"]["prompts"][0]["slug"] == "exported-prompt"

    async def test_dry_run_import_creates_nothing(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        manifest = {
            "agentos_version": "1.0",
            "resources": {
                "agents": [{"name": "Imported Agent", "model_name": "gpt-4o"}],
                "workflows": [],
                "prompts": [],
                "tools": [],
            },
        }
        resp = await client.post(
            f"/api/v1/workspaces/{ws}/iac/import",
            json={"manifest": manifest, "dry_run": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True
        assert data["would_import"]["agents"] == 1

        agents = await client.get(f"/api/v1/workspaces/{ws}/agents/", headers=auth_headers)
        assert len(agents.json()) == 0

    async def test_real_import_creates_resources(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        manifest = {
            "agentos_version": "1.0",
            "resources": {
                "tools": [{"name": "Imported Tool", "slug": "imp-tool", "description": "d"}],
                "agents": [{"name": "Imported Agent", "model_name": "gpt-4o", "tool_refs": ["imp-tool"]}],
                "workflows": [],
                "prompts": [],
            },
        }
        resp = await client.post(
            f"/api/v1/workspaces/{ws}/iac/import",
            json={"manifest": manifest, "dry_run": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["imported"] == {"agents": 1, "workflows": 0, "prompts": 0, "tools": 1}

        agents = await client.get(f"/api/v1/workspaces/{ws}/agents/", headers=auth_headers)
        assert len(agents.json()) == 1
        assert agents.json()[0]["name"] == "Imported Agent"

    async def test_unsupported_version_rejected(self, client, auth_headers, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/iac/import",
            json={"manifest": {"agentos_version": "99.0", "resources": {}}, "dry_run": False},
            headers=auth_headers,
        )
        assert resp.json()["success"] is False

    async def test_yaml_import(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        yaml_text = (
            "agentos_version: \"1.0\"\n"
            "resources:\n"
            "  agents:\n"
            "    - name: YAML Agent\n"
            "      model_name: gpt-4o\n"
            "  workflows: []\n"
            "  prompts: []\n"
            "  tools: []\n"
        )
        resp = await client.post(
            f"/api/v1/workspaces/{ws}/iac/import/yaml",
            content=yaml_text,
            headers={**auth_headers, "Content-Type": "text/plain"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is True
        assert resp.json()["imported"]["agents"] == 1

    async def test_yaml_import_invalid_syntax_400(self, client, auth_headers, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/iac/import/yaml",
            content="agents: [unclosed",
            headers={**auth_headers, "Content-Type": "text/plain"},
        )
        assert resp.status_code == 400


# ─── Auto-execution with LLM judge ───────────────────


async def _fake_judge_gateway(db, request, workspace_id=None, agent_id=None,
                              execution_id=None, preferred_provider=None, **kwargs):
    """Canned gateway: judge prompts get a JSON verdict, everything else gets
    a plain answer. Mirrors the real sentinel when ``mode == "no-provider"``."""
    from datetime import datetime, timezone

    from app.models.mcp import LLMProvider
    from app.schemas.mcp import ChatCompletionResponse

    last_user = ""
    for m in request.messages:
        if m.role == "user":
            last_user = m.content or ""

    mode = getattr(_fake_judge_gateway, "mode", "normal")
    if mode == "no-provider":
        content = "\u26a0\ufe0f All providers unavailable. Last error: none. Your message: 'x'"
    elif "evaluation judge" in last_user:
        content = '{"score": 0.9, "passed": true, "reasoning": "Covers the refund window."}'
    else:
        content = "The refund window is 30 days."

    return ChatCompletionResponse(
        id="chatcmpl-fake",
        model=request.model,
        provider=LLMProvider.GROQ,
        choices=[{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        cost_usd=0.0001,
        created=datetime.now(timezone.utc),
    )


@pytest.fixture(autouse=True)
def _fake_eval_gateway(monkeypatch):
    from app.services import mcp_service
    monkeypatch.setattr(mcp_service, "route_chat_completion", _fake_judge_gateway)


class TestAutoExecute:
    async def _suite_with_case(self, client, headers, ws):
        suite = await _create_suite(client, headers, ws)
        resp = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/suites/{suite['id']}/test-cases",
            json={
                "input": "Refund policy question",
                "expected_output": "30 days",
                "criteria": "Mentions the refund window",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        return suite

    async def test_model_run_executes_and_judges(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        suite = await self._suite_with_case(client, auth_headers, ws)
        run = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs",
            json={"suite_id": suite["id"], "model_name": "gpt-4o"},
            headers=auth_headers,
        )
        run_id = run.json()["id"]

        resp = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs/{run_id}/execute",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "completed"
        assert data["summary"]["total"] == 1
        assert data["summary"]["passed"] == 1
        assert data["summary"]["pass_rate"] == 100.0
        result = data["results"][0]
        assert result["actual_output"] == "The refund window is 30 days."
        assert result["score"] == 0.9
        assert result["passed"] is True
        assert "refund window" in result["judge_reasoning"]

    async def test_heuristic_fallback_when_judge_unparseable(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        suite = await self._suite_with_case(client, auth_headers, ws)
        run = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs",
            json={"suite_id": suite["id"], "model_name": "gpt-4o"},
            headers=auth_headers,
        )
        run_id = run.json()["id"]

        async def _refuses_to_judge(db, request, **kwargs):
            response = await _fake_judge_gateway(db, request, **kwargs)
            if "evaluation judge" in (request.messages[-1].content or ""):
                response.choices[0]["message"]["content"] = "I cannot judge this."
            return response

        from app.services import mcp_service
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(mcp_service, "route_chat_completion", _refuses_to_judge)
        try:
            resp = await client.post(
                f"/api/v1/workspaces/{ws}/evaluations/runs/{run_id}/execute",
                headers=auth_headers,
            )
        finally:
            monkeypatch.undo()
        assert resp.status_code == 200, resp.text
        result = resp.json()["results"][0]
        assert result["passed"] is True
        assert result["score"] == 1.0  # "30 days" is a substring of the answer
        assert "Heuristic" in result["judge_reasoning"]

    async def test_agent_run_uses_execution_engine(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        suite = await self._suite_with_case(client, auth_headers, ws)
        agent = await client.post(
            f"/api/v1/workspaces/{ws}/agents",
            json={
                "name": "Eval Agent",
                "description": "runs evals",
                "system_prompt": "Answer refund questions.",
                "model_provider": "groq",
                "model_name": "llama-3.3-70b-versatile",
            },
            headers=auth_headers,
        )
        assert agent.status_code == 201, agent.text
        run = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs",
            json={"suite_id": suite["id"], "agent_id": agent.json()["id"]},
            headers=auth_headers,
        )
        run_id = run.json()["id"]

        resp = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs/{run_id}/execute",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "completed"
        result = data["results"][0]
        assert result["actual_output"] == "The refund window is 30 days."
        assert result["score"] == 0.9

        executions = await client.get(
            f"/api/v1/workspaces/{ws}/agents/{agent.json()['id']}/executions",
            headers=auth_headers,
        )
        assert executions.status_code == 200
        assert executions.json()[0]["status"] == "completed"

    async def test_no_provider_marks_case_failed_but_completes_run(self, client, auth_headers, test_workspace):
        ws = test_workspace["id"]
        suite = await self._suite_with_case(client, auth_headers, ws)
        run = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs",
            json={"suite_id": suite["id"], "model_name": "gpt-4o"},
            headers=auth_headers,
        )
        run_id = run.json()["id"]

        _fake_judge_gateway.mode = "no-provider"
        try:
            resp = await client.post(
                f"/api/v1/workspaces/{ws}/evaluations/runs/{run_id}/execute",
                headers=auth_headers,
            )
        finally:
            _fake_judge_gateway.mode = "normal"

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "completed"
        assert data["summary"]["passed"] == 0
        assert "No LLM provider" in data["results"][0]["judge_reasoning"]

    async def test_execute_requires_workspace_membership(self, client, auth_headers, second_user, test_workspace):
        ws = test_workspace["id"]
        suite = await self._suite_with_case(client, auth_headers, ws)
        run = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs",
            json={"suite_id": suite["id"], "model_name": "gpt-4o"},
            headers=auth_headers,
        )
        resp = await client.post(
            f"/api/v1/workspaces/{ws}/evaluations/runs/{run.json()['id']}/execute",
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 403
