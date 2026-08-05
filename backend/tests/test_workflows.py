"""Workflow domain integration tests: CRUD, DAG validation, execution lifecycle, approval gate."""


async def _create_workflow(client, headers, ws_id, **overrides):
    payload = {"name": "Test Workflow", **overrides}
    resp = await client.post(f"/api/v1/workspaces/{ws_id}/workflows/", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


class TestWorkflowCRUD:
    async def test_create_workflow_is_draft(self, client, auth_headers, test_workspace):
        wf = await _create_workflow(client, auth_headers, test_workspace["id"])
        assert wf["status"] == "draft"
        assert wf["version"] == 1

    async def test_create_with_valid_dag(self, client, auth_headers, test_workspace):
        dag = {
            "nodes": [{"id": "n1", "type": "agent"}, {"id": "n2", "type": "tool"}],
            "edges": [{"source": "n1", "target": "n2"}],
        }
        wf = await _create_workflow(client, auth_headers, test_workspace["id"], dag_definition=dag)
        assert wf["dag_definition"] == dag

    async def test_create_with_cyclic_dag_rejected(self, client, auth_headers, test_workspace):
        dag = {
            "nodes": [{"id": "a", "type": "agent"}, {"id": "b", "type": "tool"}],
            "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
        }
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/",
            json={"name": "Cyclic", "dag_definition": dag},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "cycle" in resp.json()["detail"].lower()

    async def test_create_with_dangling_edge_rejected(self, client, auth_headers, test_workspace):
        dag = {
            "nodes": [{"id": "a", "type": "agent"}],
            "edges": [{"source": "a", "target": "missing"}],
        }
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/",
            json={"name": "Dangling", "dag_definition": dag},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_list_and_get_workflows(self, client, auth_headers, test_workspace):
        await _create_workflow(client, auth_headers, test_workspace["id"], name="WF One")
        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/", headers=auth_headers
        )
        assert listing.status_code == 200
        assert len(listing.json()) == 1
        wid = listing.json()[0]["id"]
        one = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wid}", headers=auth_headers
        )
        assert one.status_code == 200 and one.json()["name"] == "WF One"

    async def test_update_with_invalid_dag_rejected(self, client, auth_headers, test_workspace):
        wf = await _create_workflow(client, auth_headers, test_workspace["id"])
        resp = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}",
            json={"dag_definition": {"nodes": [{"id": "a"}], "edges": []}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_delete_workflow(self, client, auth_headers, test_workspace):
        wf = await _create_workflow(client, auth_headers, test_workspace["id"])
        resp = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 204
        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/", headers=auth_headers
        )
        assert wf["id"] not in [w["id"] for w in listing.json()]


class TestWorkflowExecution:
    async def test_cannot_execute_draft(self, client, auth_headers, test_workspace):
        wf = await _create_workflow(client, auth_headers, test_workspace["id"])
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/execute",
            json={"input_data": {}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_execute_active_workflow(self, client, auth_headers, test_workspace):
        wf = await _create_workflow(client, auth_headers, test_workspace["id"])
        await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}",
            json={"status": "active"},
            headers=auth_headers,
        )
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/execute",
            json={"input_data": {"repo": "foo"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["input_data"] == {"repo": "foo"}

    async def test_execution_lifecycle(self, client, auth_headers, test_workspace):
        wf = await _create_workflow(client, auth_headers, test_workspace["id"])
        await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}",
            json={"status": "active"},
            headers=auth_headers,
        )
        eid = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/execute",
                json={},
                headers=auth_headers,
            )
        ).json()["id"]
        base = f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/executions/{eid}"

        r = await client.post(f"{base}/start?auto_run=false", headers=auth_headers)
        assert r.status_code == 200 and r.json()["status"] == "running"

        r = await client.post(f"{base}/pause", headers=auth_headers)
        assert r.status_code == 200 and r.json()["status"] == "paused"

        r = await client.post(f"{base}/resume", headers=auth_headers)
        assert r.status_code == 200 and r.json()["status"] == "running"

        r = await client.post(f"{base}/cancel", headers=auth_headers)
        assert r.status_code == 200 and r.json()["status"] == "cancelled"

    async def test_approve_requires_awaiting_approval(self, client, auth_headers, test_workspace):
        wf = await _create_workflow(client, auth_headers, test_workspace["id"])
        await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}",
            json={"status": "active"},
            headers=auth_headers,
        )
        eid = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/execute",
                json={},
                headers=auth_headers,
            )
        ).json()["id"]
        # Approving a pending (not awaiting-approval) execution must fail
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/executions/{eid}/approve",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_execution_listing(self, client, auth_headers, test_workspace):
        wf = await _create_workflow(client, auth_headers, test_workspace["id"])
        await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}",
            json={"status": "active"},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/execute",
            json={},
            headers=auth_headers,
        )
        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/executions",
            headers=auth_headers,
        )
        assert listing.status_code == 200
        assert len(listing.json()) == 1

    async def test_execution_not_found(self, client, auth_headers, test_workspace):
        wf = await _create_workflow(client, auth_headers, test_workspace["id"])
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/executions/00000000-0000-0000-0000-000000000000/start",
            headers=auth_headers,
        )
        assert resp.status_code == 404
