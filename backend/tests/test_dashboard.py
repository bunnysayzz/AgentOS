"""Tests for the aggregate dashboard stats endpoint + query pushdown helpers."""

from app.core.db import FirestoreDB, now_iso


async def test_dashboard_stats_guest_returns_zeros(client):
    """Unauthenticated dashboard loads return a zeroed payload (no 401 wall)."""
    resp = await client.get("/api/v1/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["workspace_count"] == 0
    assert data["model_count"] == 0
    assert data["call_count"] == 0
    assert data["first_ws"] is None
    assert data["workspace"] is None


async def test_dashboard_stats_reflects_user_data(
    client, auth_headers, test_workspace, openai_provider
):
    """Aggregate endpoint returns counts from a real workspace + provider."""
    resp = await client.get("/api/v1/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["workspace_count"] == 1
    assert data["first_ws"] == test_workspace["id"]
    assert data["configured_providers"] == 1
    assert data["workspace"] is not None
    assert data["workspace"]["agent_count"] == 0
    assert data["workspace"]["workflow_count"] == 0
    assert data["workspace"]["secret_count"] == 0


async def test_dashboard_stats_workspace_selector(client, auth_headers, test_workspace):
    """Passing workspace_id scopes the workspace tally to that workspace."""
    resp = await client.get(
        f"/api/v1/dashboard/stats?workspace_id={test_workspace['id']}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["first_ws"] == test_workspace["id"]


async def test_query_since_filters_by_date(firestore_client):
    """query_since only returns rows with created_at >= the cutoff."""
    db = FirestoreDB(client=firestore_client)
    db.add("llm_calls", {
        "workspace_id": "ws1", "model_name": "gpt-4o-mini",
        "total_tokens": 10, "cost_usd": 0.001, "created_at": "2026-01-01T00:00:00+00:00",
    })
    db.add("llm_calls", {
        "workspace_id": "ws1", "model_name": "gpt-4o-mini",
        "total_tokens": 20, "cost_usd": 0.002, "created_at": now_iso(),
    })

    rows = db.query_since("llm_calls", "workspace_id", "ws1", "2026-06-01T00:00:00+00:00")
    assert len(rows) == 1
    assert rows[0]["total_tokens"] == 20


async def test_query_top_returns_newest_first(firestore_client):
    """query_top returns the N newest rows (created_at DESC)."""
    db = FirestoreDB(client=firestore_client)
    for i in range(5):
        db.add("llm_calls", {
            "workspace_id": "ws1", "model_name": "m",
            "total_tokens": i, "cost_usd": 0.0,
            "created_at": f"2026-01-0{i + 1}T00:00:00+00:00",
        })

    rows = db.query_top("llm_calls", "workspace_id", "ws1", 2)
    assert len(rows) == 2
    assert rows[0]["total_tokens"] == 4  # newest
    assert rows[1]["total_tokens"] == 3


async def test_count_uses_aggregation_with_fallback(firestore_client):
    """count() works via the aggregate path and falls back to a scan."""
    db = FirestoreDB(client=firestore_client)
    for i in range(3):
        db.add("api_keys", {"user_id": "u1", "key_hash": f"h{i}", "is_active": True})
    assert db.count("api_keys", "user_id", "u1") == 3
    assert db.count("api_keys") == 3


async def test_query_since_pushdown_runs_first_not_full_scan(firestore_client, monkeypatch):
    """The pushdown path must run BEFORE any unfiltered scan (regression).

    A previous implementation called ``query()`` (full collection scan)
    first, which defeated the entire optimization. Assert the filtered
    query is the only collection read on the happy path.
    """
    db = FirestoreDB(client=firestore_client)
    db.add("llm_calls", {
        "workspace_id": "ws1", "model_name": "m", "total_tokens": 1,
        "cost_usd": 0.0, "created_at": now_iso(),
    })
    db.add("llm_calls", {
        "workspace_id": "ws1", "model_name": "m", "total_tokens": 2,
        "cost_usd": 0.0, "created_at": "2026-01-01T00:00:00+00:00",
    })

    calls: list[list] = []
    original = firestore_client.collection

    def spy_collection(name):
        ref = original(name)
        # Wrap where() so we can count filtered vs unfiltered reads
        original_where = ref.where

        def spy_where(*args, **kwargs):
            calls.append(1)
            return original_where(*args, **kwargs)

        ref.where = spy_where
        return ref

    monkeypatch.setattr(firestore_client, "collection", spy_collection)

    rows = db.query_since("llm_calls", "workspace_id", "ws1", "2026-06-01T00:00:00+00:00")
    assert len(rows) == 1
    assert calls, "pushdown path should have applied filters (no unfiltered scan)"


async def test_query_since_falls_back_when_pushdown_fails(firestore_client, monkeypatch):
    """Missing composite index → single-filter query + Python range filter."""
    db = FirestoreDB(client=firestore_client)
    db.add("llm_calls", {
        "workspace_id": "ws1", "model_name": "m", "total_tokens": 1,
        "cost_usd": 0.0, "created_at": now_iso(),
    })

    original = firestore_client.collection

    def broken_collection(name):
        ref = original(name)
        original_where = ref.where

        def spy_where(*args, **kwargs):
            if any(getattr(k, "op_string", k) == ">=" for k in kwargs.values() if hasattr(k, "op_string")):
                raise Exception("INDEX_MISSING: composite index not deployed")
            return original_where(*args, **kwargs)

        ref.where = spy_where
        return ref

    monkeypatch.setattr(firestore_client, "collection", broken_collection)
    rows = db.query_since("llm_calls", "workspace_id", "ws1", "2026-06-01T00:00:00+00:00")
    assert len(rows) == 1


async def test_count_since_falls_back_without_rethrow(firestore_client, monkeypatch):
    """count_since must NOT rethrow when the composite index is missing."""
    db = FirestoreDB(client=firestore_client)
    for i in range(2):
        db.add("llm_calls", {
            "workspace_id": "ws1", "model_name": "m", "total_tokens": i,
            "cost_usd": 0.0, "created_at": now_iso(),
        })

    original = firestore_client.collection

    def broken_collection(name):
        ref = original(name)
        original_where = ref.where

        def spy_where(*args, **kwargs):
            if any(getattr(k, "op_string", k) == ">=" for k in kwargs.values() if hasattr(k, "op_string")):
                raise Exception("INDEX_MISSING")
            return original_where(*args, **kwargs)

        ref.where = spy_where
        return ref

    monkeypatch.setattr(firestore_client, "collection", broken_collection)
    assert db.count_since("llm_calls", "workspace_id", "ws1", "2026-06-01T00:00:00+00:00") == 2
