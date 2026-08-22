"""A/B Testing service — split test prompts, compare performance metrics."""

from app.core.db import FirestoreDB, new_id, now_iso

AB_TESTS = "ab_tests"
AB_VARIANTS = "ab_variants"
AB_RESULTS = "ab_results"


# ─── Test Management ─────────────────────────────────

def create_ab_test(
    db: FirestoreDB,
    workspace_id: str,
    name: str,
    description: str | None = None,
    prompt_id: str | None = None,
    variants: list[dict] | None = None,
) -> dict:
    """Create an A/B test with variants."""
    test = {
        "id": new_id(),
        "workspace_id": workspace_id,
        "name": name,
        "description": description,
        "prompt_id": prompt_id,
        "status": "draft",
        "traffic_split": 50,  # % to variant A
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "started_at": None,
        "completed_at": None,
    }
    db.add(AB_TESTS, test)
    
    # Create variants
    if variants:
        for i, v in enumerate(variants):
            variant = {
                "id": new_id(),
                "test_id": test["id"],
                "name": v.get("name", f"Variant {chr(65 + i)}"),
                "content": v.get("content"),
                "is_control": i == 0,
                "created_at": now_iso(),
            }
            db.add(AB_VARIANTS, variant)
    
    return test


def list_ab_tests(db: FirestoreDB, workspace_id: str) -> list[dict]:
    """List all A/B tests for a workspace."""
    rows = db.query(AB_TESTS, "workspace_id", workspace_id)
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def get_ab_test(db: FirestoreDB, test_id: str) -> dict | None:
    """Get an A/B test by ID."""
    return db.get(AB_TESTS, test_id)


def start_ab_test(db: FirestoreDB, test_id: str) -> dict:
    """Start an A/B test."""
    test = db.get(AB_TESTS, test_id)
    if not test:
        from app.services.workspace_service import WorkspaceNotFoundError
        raise WorkspaceNotFoundError()
    test["status"] = "running"
    test["started_at"] = now_iso()
    test["updated_at"] = now_iso()
    db.set(AB_TESTS, test_id, test)
    return test


def stop_ab_test(db: FirestoreDB, test_id: str) -> dict:
    """Stop an A/B test."""
    test = db.get(AB_TESTS, test_id)
    if not test:
        from app.services.workspace_service import WorkspaceNotFoundError
        raise WorkspaceNotFoundError()
    test["status"] = "completed"
    test["completed_at"] = now_iso()
    test["updated_at"] = now_iso()
    db.set(AB_TESTS, test_id, test)
    return test


# ─── Variants ────────────────────────────────────────

def list_variants(db: FirestoreDB, test_id: str) -> list[dict]:
    """List all variants for an A/B test."""
    rows = db.query(AB_VARIANTS, "test_id", test_id)
    return rows


def get_variant(db: FirestoreDB, variant_id: str) -> dict | None:
    """Get a variant by ID."""
    return db.get(AB_VARIANTS, variant_id)


def update_variant(db: FirestoreDB, variant_id: str, updates: dict) -> dict:
    """Update a variant."""
    variant = db.get(AB_VARIANTS, variant_id)
    if not variant:
        from app.services.workspace_service import WorkspaceNotFoundError
        raise WorkspaceNotFoundError()
    variant.update(updates)
    db.set(AB_VARIANTS, variant_id, variant)
    return variant


# ─── Results ─────────────────────────────────────────

def record_ab_result(
    db: FirestoreDB,
    test_id: str,
    variant_id: str,
    input_text: str,
    output_text: str,
    score: float | None = None,
    latency_ms: int | None = None,
    tokens_used: int | None = None,
    user_feedback: str | None = None,
) -> dict:
    """Record a result for an A/B test variant."""
    result = {
        "id": new_id(),
        "test_id": test_id,
        "variant_id": variant_id,
        "input": input_text,
        "output": output_text,
        "score": score,
        "latency_ms": latency_ms,
        "tokens_used": tokens_used,
        "user_feedback": user_feedback,
        "created_at": now_iso(),
    }
    db.add(AB_RESULTS, result)
    return result


def get_test_results(db: FirestoreDB, test_id: str) -> dict:
    """Get aggregated results for all variants in a test."""
    variants = list_variants(db, test_id)
    
    results_by_variant = {}
    for variant in variants:
        results = db.query(AB_RESULTS, "variant_id", variant["id"])
        scores = [r.get("score") for r in results if r.get("score") is not None]
        latencies = [r.get("latency_ms") for r in results if r.get("latency_ms") is not None]
        tokens = [r.get("tokens_used") for r in results if r.get("tokens_used") is not None]
        
        results_by_variant[variant["id"]] = {
            "variant": variant,
            "total_runs": len(results),
            "avg_score": round(sum(scores) / len(scores), 3) if scores else None,
            "min_score": min(scores) if scores else None,
            "max_score": max(scores) if scores else None,
            "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
            "avg_tokens": round(sum(tokens) / len(tokens)) if tokens else None,
            "positive_feedback": sum(1 for r in results if r.get("user_feedback") == "positive"),
            "negative_feedback": sum(1 for r in results if r.get("user_feedback") == "negative"),
        }
    
    # Determine winner
    variant_results = list(results_by_variant.values())
    if len(variant_results) >= 2:
        variant_results.sort(key=lambda v: v.get("avg_score") or 0, reverse=True)
        winner = variant_results[0]
        if winner.get("avg_score") and winner["total_runs"] >= 10:
            results_by_variant["winner"] = winner["variant"]["id"]
    
    return {
        "test_id": test_id,
        "variants": results_by_variant,
        "winner": results_by_variant.get("winner"),
    }
