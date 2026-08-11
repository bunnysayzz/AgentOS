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
    """Best-effort seed of the LLM model registry (sync Firestore calls)."""
    import asyncio as _asyncio

    from app.services.mcp_service import seed_default_models

    _asyncio.run(seed_default_models(FirestoreDB()))


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

    # Agent executions that were started > 10 min ago and never finished.
    for row in db.query(agent_service.EXECUTIONS):
        if row.get("status") not in (ExecutionStatus.RUNNING.value, ExecutionStatus.PENDING.value):
            continue
        if (row.get("created_at") or "") < cutoff:
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
        if (row.get("created_at") or "") < cutoff:
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
            valid = bool(token) and token == shared
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
