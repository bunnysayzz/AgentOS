"""Tests for the startup orphan-execution reaper (app.main._reap_orphaned_executions)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.main import _reap_orphaned_executions
from app.models.agent import ExecutionStatus
from app.models.workflow import WorkflowExecutionStatus
from app.services import agent_service, workflow_service


def _iso(minutes_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


class TestReaper:
    @pytest.mark.asyncio
    async def test_reaper_uses_started_at_not_created_at(self, db_session):
        """A long-queued execution that only just started must survive; idle ones die."""
        recent = {
            "id": "exec-recent",
            "agent_id": "agent-1",
            "status": ExecutionStatus.RUNNING.value,
            "created_at": _iso(120),
            "started_at": _iso(2),
        }
        stale = {
            "id": "exec-stale",
            "agent_id": "agent-1",
            "status": ExecutionStatus.RUNNING.value,
            "created_at": _iso(120),
            "started_at": _iso(30),
        }
        queued = {
            "id": "exec-queued",
            "agent_id": "agent-1",
            "status": ExecutionStatus.PENDING.value,
            "created_at": _iso(120),
            "started_at": None,
        }
        for row in (recent, stale, queued):
            db_session.set(agent_service.EXECUTIONS, row["id"], row)

        await _reap_orphaned_executions(db_session)

        assert (
            db_session.get(agent_service.EXECUTIONS, "exec-recent")["status"]
            == ExecutionStatus.RUNNING.value
        )
        reaped = db_session.get(agent_service.EXECUTIONS, "exec-stale")
        assert reaped["status"] == ExecutionStatus.FAILED.value
        assert "restart" in reaped["error_message"]
        assert (
            db_session.get(agent_service.EXECUTIONS, "exec-queued")["status"]
            == ExecutionStatus.FAILED.value
        )

    @pytest.mark.asyncio
    async def test_reaper_leaves_awaiting_approval_workflows_parked(self, db_session):
        parked = {
            "id": "wf-parked",
            "workflow_id": "wf-1",
            "status": WorkflowExecutionStatus.AWAITING_APPROVAL.value,
            "created_at": _iso(120),
        }
        stale = {
            "id": "wf-stale",
            "workflow_id": "wf-1",
            "status": WorkflowExecutionStatus.RUNNING.value,
            "created_at": _iso(120),
            "started_at": _iso(30),
        }
        for row in (parked, stale):
            db_session.set(workflow_service.WORKFLOW_EXECUTIONS, row["id"], row)

        await _reap_orphaned_executions(db_session)

        assert (
            db_session.get(workflow_service.WORKFLOW_EXECUTIONS, "wf-parked")["status"]
            == WorkflowExecutionStatus.AWAITING_APPROVAL.value
        )
        assert (
            db_session.get(workflow_service.WORKFLOW_EXECUTIONS, "wf-stale")["status"]
            == WorkflowExecutionStatus.FAILED.value
        )
