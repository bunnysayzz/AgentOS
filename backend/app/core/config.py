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

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./agentos.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Firebase & Google Cloud
    FIREBASE_PROJECT_ID: str = "agentos-7f01e"
    FIREBASE_USER_EMAIL: str = ""
    FIREBASE_CLIENT_ID: str = ""
    FIREBASE_REFRESH_TOKEN: str = ""
    FIREBASE_ACCESS_TOKEN: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

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

    # First superuser (auto-created on startup)
    FIRST_SUPERUSER_EMAIL: str = ""
    FIRST_SUPERUSER_PASSWORD: str = ""


settings = Settings()
