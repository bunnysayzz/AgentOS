"""AgentOS Studio - FastAPI Application Entry Point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import engine, Base, async_session_factory
from app.api import router as api_router


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
    """Application lifespan with startup and shutdown events."""
    # Startup: create tables (in production use Alembic migrations)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Auto-seed first superuser if configured
    if settings.FIRST_SUPERUSER_EMAIL and settings.FIRST_SUPERUSER_PASSWORD:
        try:
            from sqlalchemy import select
            from app.models.user import User
            from app.core.security import hash_password

            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.email == settings.FIRST_SUPERUSER_EMAIL)
                )
                existing = result.scalar_one_or_none()
                if existing is None:
                    user = User(
                        email=settings.FIRST_SUPERUSER_EMAIL,
                        username=settings.FIRST_SUPERUSER_EMAIL.split("@")[0],
                        full_name="Super Admin",
                        hashed_password=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
                        is_active=True,
                        is_verified=True,
                        is_superuser=True,
                    )
                    session.add(user)
                    await session.commit()
                    print(f"✅ Created first superuser: {settings.FIRST_SUPERUSER_EMAIL}")
                else:
                    print(f"✅ First superuser already exists: {settings.FIRST_SUPERUSER_EMAIL}")
        except Exception as e:
            print(f"⚠️  Could not auto-create superuser: {e}")

    yield
    # Shutdown: dispose of engine
    await engine.dispose()


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
    if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
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
