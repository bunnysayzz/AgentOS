"""Alembic environment configuration (legacy — unused at runtime).

AgentOS Studio no longer uses a SQL database: all data lives in Cloud
Firestore, and production boots directly from ``entrypoint.sh`` without
running migrations. This file exists only so ``alembic`` can still be run
manually for legacy tooling. It never connects to a remote database — it
falls back to a local SQLite file so nothing ever reaches out to an
external Postgres (e.g. the decommissioned Aiven instance).
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.database import Base

# Import all models so Alembic can detect them
import app.models  # noqa: F401

config = context.config

# Never read a DATABASE_URL from env — stay on the local SQLite fallback
# declared in alembic.ini so legacy tooling can't touch a remote database.

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    # Local SQLite only — see module docstring (no remote database).
    configuration["sqlalchemy.url"] = config.get_main_option("sqlalchemy.url")
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
