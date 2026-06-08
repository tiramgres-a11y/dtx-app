# -*- coding: utf-8 -*-
"""
Alembic env.py — configured for DTx backend.

Uses DTX_DATABASE_URL env var (falls back to local PostgreSQL default).
Imports Base.metadata from backend.models so autogenerate can diff all tables.
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------------
# Alembic Config object
# ---------------------------------------------------------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Inject DATABASE_URL from environment (overrides alembic.ini placeholder)
# ---------------------------------------------------------------------------

_db_url = os.getenv(
    "DTX_DATABASE_URL",
    "postgresql+psycopg2://dtx:dtx@localhost:5432/dtx",
)
config.set_main_option("sqlalchemy.url", _db_url)

# ---------------------------------------------------------------------------
# Import models so Base.metadata is populated for autogenerate
# ---------------------------------------------------------------------------

import backend.models  # noqa: F401, E402
from backend.database import Base  # noqa: E402

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline (SQL script) migrations
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (requires live DB connection)
# ---------------------------------------------------------------------------


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
