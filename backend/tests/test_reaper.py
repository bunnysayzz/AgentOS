"""Tests for the startup reaper that fails executions orphaned by restarts."""

import pytest

from app.core.db import FirestoreDB, stamp
from app.models.agent import ExecutionStatus
from app.models.workflow import WorkflowExecutionStatus
from app.services import agent_service, workflow_service


@pytest.mark.asyncio
async def test_reaper_fails_orphaned_running_agent_executions(db_session: FirestoreDB):
    from app.main import _reap_orphaned_executions

    from datetime import datetime, timedelta, timezone

    # A stale RUNNING execution from "before a restart".
    stale = stamp({
        "agent_id": "a1",
        "session_id": "s",
        "status": ExecutionStatus.RUNNING.value,
        "input_data": {"input": "x"},
        "created_at": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
    })
    db_session.add(agent_service.EXECUTIONS, stale)

    # A fresh RUNNING execution that must NOT be reaped.
    fresh = stamp({
        "agent_id": "a2",
        "session_id": "s2",
        "status": ExecutionStatus.RUNNING.value,
        "input_data": {"input": "y"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    db_session.add(agent_service.EXECUTIONS, fresh)

    await _reap_orphaned_executions(db=db_session)

    reaped = await agent_service.get_execution_by_id(db_session, stale["id"])
    assert reaped["status"] == ExecutionStatus.FAILED.value
    assert "restart" in (reaped["error_message"] or "")

    untouched = await agent_service.get_execution_by_id(db_session, fresh["id"])
    assert untouched["status"] == ExecutionStatus.RUNNING.value


@pytest.mark.asyncio
async def test_reaper_preserves_parked_approvals(db_session: FirestoreDB):
    from app.main import _reap_orphaned_executions

    from datetime import datetime, timedelta, timezone

    parked = stamp({
        "workflow_id": "w1",
        "status": WorkflowExecutionStatus.AWAITING_APPROVAL.value,
        "triggered_by": "t",
        "created_at": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
    })
    db_session.add(workflow_service.WORKFLOW_EXECUTIONS, parked)

    await _reap_orphaned_executions(db=db_session)

    still = await workflow_service.get_execution(db_session, parked["id"])
    assert still["status"] == WorkflowExecutionStatus.AWAITING_APPROVAL.value
