# -*- coding: utf-8 -*-
"""
Alembic env.py — configured for Lumen Health backend.

URL priority (first match wins):
  1. DATABASE_URL     env var — set by Render / production host
  2. DTX_DATABASE_URL env var — legacy local-dev name (backward compat)
  3. sqlite:///./dtx.db       — zero-config fallback

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

# Mirror the same priority logic used in backend/database.py.
_db_url: str = (
    os.getenv("DATABASE_URL")
    or os.getenv("DTX_DATABASE_URL")
    or "sqlite:///./dtx.db"
)

# Normalise legacy postgres:// → postgresql:// (SQLAlchemy 1.4+ requirement).
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

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
