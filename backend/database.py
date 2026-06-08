# -*- coding: utf-8 -*-
"""
database.py — SQLAlchemy engine, session factory, and declarative base.

Production URI : postgresql+psycopg2://dtx:dtx@localhost:5432/dtx
Test URI       : sqlite:///:memory:  (injected via override_get_db in tests)

The module exposes:
  engine         — SQLAlchemy Engine (production Postgres)
  SessionLocal   — sessionmaker factory (call to get a Session)
  Base           — declarative base for all ORM models
  get_db()       — FastAPI dependency that yields a scoped Session,
                   commits on success, rolls back on exception,
                   and always closes the session.
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ---------------------------------------------------------------------------
# Database URL
# ---------------------------------------------------------------------------

# Production: postgresql+psycopg2://dtx:dtx@localhost:5432/dtx
# Override via DTX_DATABASE_URL environment variable in production.
DATABASE_URL: str = os.getenv(
    "DTX_DATABASE_URL",
    "postgresql+psycopg2://dtx:dtx@localhost:5432/dtx",
)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

# connect_args is only needed for SQLite (check_same_thread=False).
# For Postgres the dict is empty.
_connect_args: dict = (
    {"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,          # verify connections before checkout
    echo=False,                  # set True to log all SQL
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,      # avoid lazy-load after commit in FastAPI
)

# ---------------------------------------------------------------------------
# Declarative base (shared by all ORM models)
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


# ---------------------------------------------------------------------------
# FastAPI dependency — yields a scoped DB session per request
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that:
      1. Opens a SQLAlchemy Session from SessionLocal.
      2. Yields it to the route handler.
      3. Commits on success (no exception raised by the handler).
      4. Rolls back on any exception — ensures atomicity.
      5. Always closes the session (connection returned to pool).

    Usage in routes:
        from fastapi import Depends
        from backend.database import get_db

        @router.post("/endpoint")
        async def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
