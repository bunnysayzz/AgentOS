"""AgentOS Studio - FastAPI Application Entry Point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base, async_session_factory
from app.api import router as api_router


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

# API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "service": settings.PROJECT_NAME,
    }
