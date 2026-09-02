"""AgentOS Studio - FastAPI Application Entry Point."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.db import FirestoreDB
from app.api import router as api_router


# ─── Sentry error tracking (env-gated) ────────────────────────────────
# Unhandled exceptions in production get reported with full stack traces;
# local dev (no SENTRY_DSN) is untouched. Toggle via env, never hardcoded.
if settings.SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        environment="production" if not settings.DEBUG else "development",
        release=settings.VERSION,
        # Don't send raw API keys / secrets stored in request bodies.
        send_default_pii=False,
    )


def _frontend_dist_dir() -> Path | None:
    """Resolve the built frontend directory, if it exists.

    Supports both a configured FRONTEND_DIST env var (absolute or relative to
    the repo root) and the default ``frontend/dist`` inside the repo. When the
    build is absent (e.g. API-only mode or tests), returns None so the app
    simply doesn't serve the SPA.
    """
    repo_root = Path(__file__).resolve().parents[2]
    configured = (settings.FRONTEND_DIST or "").strip()
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        return candidate if candidate.is_dir() else None

    default = repo_root / "frontend" / "dist"
    return default if default.is_dir() else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with startup and shutdown events.

    All startup warmups are best-effort and run as BOUNDED BACKGROUND TASKS in
    worker threads — they are never awaited inline. Firestore calls are
    synchronous and can retry for 10+ minutes when a credential is dead
    (expired/revoked refresh token). Awaiting them here was the root cause of
    Render "Port scan timeout" deploy failures: the server never got a chance
    to bind its port. With this design the port binds immediately and a broken
    credential only degrades data endpoints, never startup.
    """
    warmup_tasks = [
        _spawn_bounded_warmup("model registry seed", _seed_models_sync),
        _spawn_bounded_warmup("firebase cert warmup", _warm_certs_sync),
        _spawn_bounded_warmup("execution reaper", _reap_sync),
        _spawn_bounded_warmup("agentrouter provider seed", _seed_agentrouter_sync),
    ]

    # Cron scheduler for schedule-triggered workflows (runs while the process
    # is alive; cancelled cleanly on shutdown).
    scheduler_task = None
    if settings.SCHEDULER_ENABLED:
        try:
            from app.core.scheduler import run_scheduler
            scheduler_task = asyncio.create_task(
                run_scheduler(FirestoreDB(), settings.SCHEDULER_INTERVAL_SECONDS)
            )
        except Exception as e:
            print(f"⚠️  Workflow scheduler skipped: {e}")

    yield

    if scheduler_task:
        scheduler_task.cancel()
    for task in warmup_tasks:
        task.cancel()


def _spawn_bounded_warmup(label: str, fn) -> asyncio.Task:
    """Run a startup warmup off the event loop, hard-bounded by a timeout.

    Firestore calls are synchronous (google-cloud-firestore) and block the
    calling thread — with a dead/expired credential gRPC retries for minutes.
    Running the work in ``to_thread`` and bounding it with ``wait_for`` means
    startup NEVER blocks on Firebase, and a hung warmup is abandoned instead of
    stalling the whole service (the Render "Port scan timeout" failure mode).
    """
    timeout = settings.STARTUP_WARMUP_TIMEOUT_SECONDS

    async def runner():
        try:
            await asyncio.wait_for(asyncio.to_thread(fn), timeout=timeout)
            print(f"✅ {label} complete")
        except asyncio.TimeoutError:
            print(f"⚠️  {label} timed out after {timeout:.0f}s — continuing without it")
        except Exception as e:
            print(f"⚠️  {label} skipped: {e}")

    return asyncio.create_task(runner())


def _seed_models_sync() -> None:
    """Best-effort seed of the LLM model registry (sync Firestore calls).

    Only seeds if the registry is EMPTY — never overwrites existing data.
    """
    import asyncio as _asyncio

    try:
        from app.services.mcp_service import seed_default_models
        _asyncio.run(seed_default_models(FirestoreDB()))
    except Exception as e:
        print(f"⚠️  Model registry seed skipped: {e}")


def _seed_agentrouter_sync() -> None:
    """Auto-seed providers from env vars (AGENTROUTER_API_KEY, etc.)."""
    import asyncio as _asyncio

    from app.core.config import settings
    from app.services import provider_service
    from app.services.provider_metadata import get_provider_metadata
    from app.schemas.mcp import ProviderConfigCreate
    from app.models.mcp import LLMProvider

    db = FirestoreDB()
    seeded = 0

    # Map of env var -> (LLMProvider, base_url override, default_model override)
    env_providers = [
        (settings.AGENTROUTER_API_KEY, LLMProvider.AGENTROUTER,
         settings.AGENTROUTER_BASE_URL or "https://deepseek-console-913582f071dc.herokuapp.com/v1",
         "deepseek/deepseek-v4-flash"),
        (settings.OPENAI_API_KEY, LLMProvider.OPENAI, None, None),
        (settings.ANTHROPIC_API_KEY, LLMProvider.ANTHROPIC, None, None),
        (settings.GOOGLE_API_KEY, LLMProvider.GOOGLE, None, None),
        (settings.GROQ_API_KEY, LLMProvider.GROQ, None, None),
        (settings.MISTRAL_API_KEY, LLMProvider.MISTRAL, None, None),
        (settings.CEREBRAS_API_KEY, LLMProvider.CEREBRAS, None, None),
        (settings.DEEPSEEK_API_KEY, LLMProvider.DEEPSEEK, None, None),
        (settings.XAI_API_KEY, LLMProvider.XAI, None, None),
        (settings.COHERE_API_KEY, LLMProvider.COHERE, None, None),
        (settings.PERPLEXITY_API_KEY, LLMProvider.PERPLEXITY, None, None),
        (settings.TOGETHER_API_KEY, LLMProvider.TOGETHERAI, None, None),
        (settings.FIREWORKS_API_KEY, LLMProvider.FIREWORKS, None, None),
        (settings.DEEPINFRA_API_KEY, LLMProvider.DEEPINFRA, None, None),
        (settings.HUGGINGFACE_API_KEY, LLMProvider.HUGGINGFACE, None, None),
        (settings.OPENROUTER_API_KEY, LLMProvider.OPENROUTER, None, None),
        (settings.NVIDIA_API_KEY, LLMProvider.NVIDIA_NIM, None, None),
        (settings.NOVITA_API_KEY, LLMProvider.NOVITA, None, None),
        (settings.SAMBANOVA_API_KEY, LLMProvider.SAMBANOVA, None, None),
        (settings.HYPERBOLIC_API_KEY, LLMProvider.HYPERBOLIC, None, None),
        (settings.DATABRICKS_TOKEN, LLMProvider.DATABRICKS, None, None),
        (settings.DIGITALOCEAN_ACCESS_TOKEN, LLMProvider.DIGITALOCEAN, None, None),
        (settings.MOONSHOT_API_KEY, LLMProvider.MOONSHOTAI, None, None),
        (settings.VENICE_API_KEY, LLMProvider.VENICE, None, None),
        (settings.POOLSIDE_API_KEY, LLMProvider.POOLSIDE, None, None),
        (settings.IOINTELLIGENCE_API_KEY, LLMProvider.IO_NET, None, None),
        (settings.NEBIUS_API_KEY, LLMProvider.NEBIUS, None, None),
        (settings.SCALEWAY_API_KEY, LLMProvider.SCALEWAY, None, None),
        (settings.OVHCLOUD_API_KEY, LLMProvider.OVHCLOUD, None, None),
        (settings.HELICONE_API_KEY, LLMProvider.HELICONE, None, None),
        (settings.MODAL_PROXY_TOKEN, LLMProvider.MODAL, None, None),
        (settings.BASETEN_API_KEY, LLMProvider.BASETEN, None, None),
        (settings.CORTECS_API_KEY, LLMProvider.CORTECS, None, None),
        (settings.LLAMA_API_KEY, LLMProvider.LLAMA, None, None),
        (settings.OLLAMA_API_KEY, LLMProvider.OLLAMA_CLOUD, None, None),
        (settings.OPENCODE_API_KEY, LLMProvider.OPENCODE, None, None),
        (settings.UPSTAGE_API_KEY, LLMProvider.UPSTAGE, None, None),
        (settings.SILICONFLOW_API_KEY, LLMProvider.SILICONFLOW, None, None),
        (settings.DASHSCOPE_API_KEY, LLMProvider.ALIBABA, None, None),
        (settings.ZHIPU_API_KEY, LLMProvider.Z_AI, None, None),
        (settings.STEPFUN_API_KEY, LLMProvider.STEPFUN, None, None),
        (settings.FRIENDLI_TOKEN, LLMProvider.FRIENDLI, None, None),
        (settings.CRUSOE_API_KEY, LLMProvider.CRUSOE, None, None),
        (settings.MEGANOVA_API_KEY, LLMProvider.MEGANOVA, None, None),
        (settings.CHUTES_API_KEY, LLMProvider.CHUTES, None, None),
        (settings.KILO_API_KEY, LLMProvider.KILO, None, None),
        (settings.AI_302_API_KEY, LLMProvider.AI_302, None, None),
        (settings.ABACUS_API_KEY, LLMProvider.ABACUS, None, None),
        (settings.REGOLO_API_KEY, LLMProvider.REGOLO, None, None),
        (settings.REQUESTY_API_KEY, LLMProvider.REQUESTY, None, None),
        (settings.ZENMUX_API_KEY, LLMProvider.ZENMUX, None, None),
        (settings.SARVAM_API_KEY, LLMProvider.SARVAM, None, None),
        (settings.SCX_API_KEY, LLMProvider.SCX_AI, None, None),
        (settings.INFERENCE_API_KEY, LLMProvider.INFERENCE, None, None),
        (settings.GITHUB_TOKEN, LLMProvider.GITHUB_COPILOT, None, None),
        (settings.GITLAB_TOKEN, LLMProvider.GITLAB, None, None),
    ]

    # SAFETY: First do a dry-run to check if ANY providers already exist.
    # If Firestore is unreachable or slow, we MUST NOT seed — creating fresh
    # configs would overwrite the user's manually-configured keys.
    try:
        all_configs = _asyncio.run(provider_service.list_provider_configs(db))
        configured_slugs = {c.get("provider") for c in all_configs if c.get("encrypted_api_key")}
    except Exception as e:
        print(f"⚠️  Provider auto-seed skipped: Firestore unreachable ({e})")
        return

    for api_key, provider_enum, base_url_override, default_model in env_providers:
        api_key = (api_key or "").strip()
        if not api_key:
            continue

        # NEVER overwrite a provider the user already configured
        if provider_enum.value in configured_slugs:
            continue

        meta = get_provider_metadata(provider_enum)
        base_url = base_url_override or meta.get("base_url") or None
        default_model = default_model or meta.get("default_model") or None

        _asyncio.run(provider_service.upsert_provider_config(
            db,
            ProviderConfigCreate(
                provider=provider_enum,
                api_key=api_key,
                base_url=base_url,
                default_model=default_model,
            ),
        ))
        seeded += 1

    if seeded:
        print(f"✅ Seeded {seeded} provider(s) from env vars")


def _warm_certs_sync() -> None:
    """Warm the Firebase ID-token signing-cert cache (network call)."""
    from app.core.firebase import _fetch_firebase_certs

    _fetch_firebase_certs()


def _reap_sync() -> None:
    """Reap executions orphaned by a previous process restart."""
    import asyncio as _asyncio

    _asyncio.run(_reap_orphaned_executions())


async def _reap_orphaned_executions(db: FirestoreDB | None = None) -> None:
    """Fail executions still in-flight from before a restart.

    Pass a ``db`` handle for tests; defaults to the live Firestore wrapper.
    """
    from datetime import datetime, timedelta, timezone

    from app.models.agent import ExecutionStatus
    from app.models.workflow import WorkflowExecutionStatus
    from app.services import agent_service, workflow_service

    db = db or FirestoreDB()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    reaped = 0

    # Agent executions that have been idle since before the cutoff. Use
    # started_at (falling back to created_at for never-started PENDING rows)
    # so a long-queued execution that only just began is not reaped.
    for row in db.query(agent_service.EXECUTIONS):
        if row.get("status") not in (ExecutionStatus.RUNNING.value, ExecutionStatus.PENDING.value):
            continue
        if (row.get("started_at") or row.get("created_at") or "") < cutoff:
            row["status"] = ExecutionStatus.FAILED.value
            row["error_message"] = "Execution interrupted by service restart"
            row["completed_at"] = datetime.now(timezone.utc).isoformat()
            db.set(agent_service.EXECUTIONS, row["id"], row)
            reaped += 1

    # Same for workflow executions (respect approvals — leave those parked).
    for row in db.query(workflow_service.WORKFLOW_EXECUTIONS):
        if row.get("status") not in (
            WorkflowExecutionStatus.RUNNING.value,
            WorkflowExecutionStatus.PENDING.value,
        ):
            continue
        if (row.get("started_at") or row.get("created_at") or "") < cutoff:
            row["status"] = WorkflowExecutionStatus.FAILED.value
            row["error_message"] = "Execution interrupted by service restart"
            row["completed_at"] = datetime.now(timezone.utc).isoformat()
            db.set(workflow_service.WORKFLOW_EXECUTIONS, row["id"], row)
            reaped += 1

    if reaped:
        print(f"♻️  Reaped {reaped} orphaned execution(s) from the previous run")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-grade IDE for agentic AI systems",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (per-IP sliding window; in-memory, single-instance safe)
from app.core.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# Security hardening headers (CSP, X-Frame-Options, HSTS, nosniff, …)
from app.core.security_headers import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)


# ─── Real MCP protocol server ────────────────────────────────
# External MCP clients (Claude Desktop, Cursor, MCP Inspector…) connect at
# /mcp via the Streamable HTTP transport. Auth: Bearer API key, or the
# configured MCP_ACCESS_TOKEN shared secret.


def _mcp_auth_middleware(mcp_app):
    """ASGI middleware: require a valid Bearer API key (or MCP_ACCESS_TOKEN)."""
    import hmac

    from starlette.responses import JSONResponse

    async def mcp_auth(scope, receive, send):
        if scope["type"] != "http":
            await mcp_app(scope, receive, send)
            return

        headers = {
            k.decode("latin1").lower(): v.decode("latin1")
            for k, v in scope.get("headers", [])
        }
        auth = headers.get("authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""

        shared = (settings.MCP_ACCESS_TOKEN or "").strip()
        if shared:
            # Constant-time compare — never leak the shared secret via timing.
            valid = bool(token) and hmac.compare_digest(token, shared)
        elif token.startswith("agos_"):  # cheap pre-check before touching Firestore
            from app.services import api_key_service
            db = FirestoreDB()
            valid = api_key_service.verify_api_key(db, token) is not None
        else:
            valid = False

        if not valid:
            response = JSONResponse(
                {
                    "detail": (
                        "Unauthorized — provide a valid API key "
                        "or configure MCP_ACCESS_TOKEN"
                    )
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return
        await mcp_app(scope, receive, send)

    return mcp_auth


if settings.MCP_ENABLED:
    try:
        from app.services.mcp_server import mcp as agentos_mcp
        app.mount("/mcp", _mcp_auth_middleware(agentos_mcp.streamable_http_app()), name="mcp")
    except Exception as e:
        print(f"⚠️  MCP server mount skipped: {e}")

# ─── Firebase auth-helper proxy (same-origin Google sign-in) ──────────────
# Transparently serves /__/auth and /__/firebase from <project>.firebaseapp.com
# ON OUR OWN origin. Browsers that block third-party storage (Safari ITP,
# Chrome 115+, Firefox 109+) break cross-origin Google sign-in; proxying makes
# the auth iframe same-origin so sign-in works everywhere. MUST be registered
# before the SPA /{full_path:path} catch-all below.
from app.core.auth_proxy import register_auth_proxy
register_auth_proxy(app)


@app.middleware("http")
async def cache_control_headers(request: Request, call_next):
    """Cache-control hardening.

    Prevents stale content (a pre-deploy 404, or an old SPA shell) from being
    served from a browser or edge CDN cache after a redeploy:

    - /assets/*  (content-hashed filenames)  → cache forever (immutable)
    - /api/*, /health, /docs, /redoc         → never cache (dynamic JSON/UI)
    - everything else (SPA shell, /admin)    → always revalidate
    """
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith(("/api/", "/docs", "/redoc")) or path in ("/health", "/openapi.json"):
        response.headers["Cache-Control"] = "no-store"
    else:
        response.headers["Cache-Control"] = "no-cache"
    return response


# API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "service": settings.PROJECT_NAME,
    }


# ─── Single-service frontend hosting ───────────────────────────────
# When the frontend has been built (frontend/dist), the backend serves the
# SPA at the site root so a single Render service hosts both the UI and the
# API. The API console stays available at /admin (Swagger UI).

frontend_dist = _frontend_dist_dir()

if frontend_dist is not None:
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


@app.api_route("/admin", methods=["GET", "HEAD"], include_in_schema=False)
async def admin_console():
    """Backend admin console — the interactive API docs (Swagger UI)."""
    return RedirectResponse("/docs")


@app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def spa_fallback(full_path: str):
    """Serve the SPA for client-side routes (only when the build exists)."""
    if full_path.startswith(("api/", "docs", "redoc", "openapi.json", "__/")):
        raise HTTPException(status_code=404, detail="Not found")
    if frontend_dist is None:
        raise HTTPException(status_code=404, detail="Frontend build not present")

    # Serve real static files (favicon, manifest, etc.) if they exist
    candidate = frontend_dist / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)

    # Otherwise fall back to index.html for client-side routing
    index_html = frontend_dist / "index.html"
    if index_html.is_file():
        return FileResponse(index_html)
    raise HTTPException(status_code=404, detail="Frontend build not present")
