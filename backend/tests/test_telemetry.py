"""Telemetry & audit integration tests: events, filtering, stats, audit logs."""

import uuid
from uuid import UUID

from app.models.telemetry import AuditAction
from app.services import telemetry_service


class TestTelemetryEvents:
    async def test_create_event(self, client, auth_headers, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/events",
            json={
                "event_name": "agent.execution.completed",
                "event_type": "agent",
                "severity": "info",
                "duration_ms": 120,
                "cost_usd": 0.002,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["event_name"] == "agent.execution.completed"
        assert data["severity"] == "info"

    async def test_list_events(self, client, auth_headers, test_workspace):
        for name in ["evt.one", "evt.two"]:
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/events",
                json={"event_name": name, "event_type": "agent", "severity": "info"},
                headers=auth_headers,
            )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/events", headers=auth_headers
        )
        assert resp.status_code == 200
        names = [e["event_name"] for e in resp.json()]
        assert "evt.one" in names and "evt.two" in names

    async def test_filter_events_by_severity(self, client, auth_headers, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/events",
            json={"event_name": "warn.evt", "event_type": "agent", "severity": "warning"},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/events",
            json={"event_name": "err.evt", "event_type": "agent", "severity": "error"},
            headers=auth_headers,
        )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/events",
            params={"severity": "error"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) == 1
        assert events[0]["event_name"] == "err.evt"

    async def test_get_event_by_id(self, client, auth_headers, test_workspace):
        event = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/events",
                json={"event_name": "single.evt", "event_type": "agent", "severity": "info"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/events/{event['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == event["id"]

    async def test_get_missing_event_404(self, client, auth_headers, test_workspace):
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/events/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_events_isolated_per_workspace(self, client, auth_headers, second_user, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/events",
            json={"event_name": "private.evt", "event_type": "agent", "severity": "info"},
            headers=auth_headers,
        )
        other_ws = (
            await client.post("/api/v1/workspaces/", json={"name": "Other"}, headers=second_user["auth_headers"])
        ).json()
        resp = await client.get(
            f"/api/v1/workspaces/{other_ws['id']}/events", headers=second_user["auth_headers"]
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestStats:
    async def test_workspace_stats(self, client, auth_headers, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/events",
            json={"event_name": "a", "event_type": "agent", "severity": "info"},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/events",
            json={"event_name": "b", "event_type": "workflow", "severity": "error"},
            headers=auth_headers,
        )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/events/stats",
            params={"days": 7},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_events"] == 2
        assert data["errors"] == 1
        assert data["events_by_type"]["agent"] == 1
        assert data["events_by_type"]["workflow"] == 1


class TestAuditLogs:
    async def test_audit_logs_empty_listing(self, client, auth_headers, test_workspace):
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/audit-logs", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_audit_logs_listing_with_service_recorded(self, client, auth_headers, test_workspace, db_session):
        me = await client.get("/api/v1/auth/me", headers=auth_headers)
        await telemetry_service.create_audit_log(
            db_session,
            workspace_id=UUID(test_workspace["id"]),
            user_id=UUID(me.json()["id"]),
            action=AuditAction.CREATE,
            resource_type="agent",
            resource_id="agent-123",
        )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/audit-logs", headers=auth_headers
        )
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) == 1
        assert logs[0]["action"] == "create"
        assert logs[0]["resource_type"] == "agent"
