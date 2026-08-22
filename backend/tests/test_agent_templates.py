"""Agent templates: catalog endpoint and one-click creation from template."""


class TestAgentTemplates:
    async def test_list_templates(self, client, auth_headers):
        resp = await client.get("/api/v1/templates", headers=auth_headers)
        assert resp.status_code == 200
        templates = resp.json()
        ids = {t["id"] for t in templates}
        assert "support-agent" in ids
        assert "data-analyst" in ids
        assert len(templates) >= 4
        # Every template must carry the fields the UI needs
        for t in templates:
            assert t["name"]
            assert t["system_prompt"]
            assert t["model_name"]
            assert t["model_provider"]

    async def test_templates_public_no_auth(self, client):
        # Templates are a catalog, not private data — must work without auth.
        resp = await client.get("/api/v1/templates/")
        assert resp.status_code == 200

    async def test_create_from_template(self, client, auth_headers, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/from-template",
            json={"template_id": "support-agent"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        agent = resp.json()
        assert agent["name"] == "Support Agent"
        assert "customer" in (agent["system_prompt"] or "").lower()
        assert agent["model_name"] == "gpt-4o"
        assert agent["status"] == "draft"

    async def test_create_from_unknown_template_404(self, client, auth_headers, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/from-template",
            json={"template_id": "does-not-exist"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_create_from_template_requires_member(self, client, second_user, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/from-template",
            json={"template_id": "support-agent"},
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 403
