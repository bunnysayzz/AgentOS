"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Project
    PROJECT_NAME: str = "AgentOS Studio"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Firebase & Google Cloud
    FIREBASE_PROJECT_ID: str = "agentos-7f01e"
    FIREBASE_USER_EMAIL: str = ""
    FIREBASE_CLIENT_ID: str = ""
    FIREBASE_REFRESH_TOKEN: str = ""
    FIREBASE_ACCESS_TOKEN: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # Production-grade Firebase auth: paste the entire service-account JSON
    # (Firebase Console → Project settings → Service accounts → Generate new
    # private key). When set, it is used FIRST — above the refresh-token path.
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""

    # Transparent reverse-proxy target for the Firebase auth sign-in helpers
    # (/__/auth, /__/firebase). Defaults to <project>.firebaseapp.com. Serving
    # them SAME-origin on the app domain is Firebase's documented fix for
    # browsers that block third-party storage (Safari ITP etc.) breaking
    # Google sign-in — see app/core/auth_proxy.py.
    FIREBASE_AUTH_PROXY_TARGET: str = ""

    # Security
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # LLM Provider defaults
    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_LLM_MODEL: str = "gpt-4o"

    # Storage
    ARTIFACT_STORAGE_PATH: str = "./data/artifacts"
    WORKSPACE_STORAGE_PATH: str = "./data/workspaces"

    # Frontend static build (served at / when present — single-service deploy)
    FRONTEND_DIST: str = ""

    # Encryption
    ENCRYPTION_KEY: str = "change-me-in-production-32bytes-long-key!"

    # First superuser — their Firestore user doc is flagged is_superuser on
    # first Firebase authentication (no password stored server-side).
    FIRST_SUPERUSER_EMAIL: str = ""

    # Error tracking (Sentry) — when set, unhandled exceptions are reported
    # with stack traces. Leave empty to disable (no-op in local dev).
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # CSP extensions — extra hosts the SPA may need to reach (e.g. a
    # self-hosted analytics script). The strict CSP defaults already allow
    # Google Fonts, Firebase Auth/Storage and Sentry ingest; add any other
    # first-party script/connect host here (space-separated).
    CSP_EXTRA_SCRIPT_SRC: str = ""
    CSP_EXTRA_CONNECT_SRC: str = ""

    # Rate limiting (per-IP sliding window)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH_PER_MIN: int = 20
    RATE_LIMIT_CHAT_PER_MIN: int = 60
    RATE_LIMIT_DEFAULT_PER_MIN: int = 300

    # Workflow scheduler (cron triggers, runs in-process while the service is up)
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_INTERVAL_SECONDS: int = 60

    # Hard cap (seconds) on each startup warmup (model-registry seed, Firebase
    # cert cache, orphan reaper). Warmups run in background worker threads and
    # are abandoned when they exceed this — a dead/expired Firebase credential
    # (gRPC retries for minutes) must NEVER block the server from binding its
    # port, or Render marks the deploy "Timed out" (port scan timeout).
    STARTUP_WARMUP_TIMEOUT_SECONDS: float = 10.0

    # MCP protocol server (external MCP clients connect at /mcp)
    MCP_ENABLED: bool = True
    # Optional shared secret for MCP HTTP auth (when unset, API keys are used)
    MCP_ACCESS_TOKEN: str = ""


settings = Settings()
