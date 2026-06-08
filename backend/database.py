# -*- coding: utf-8 -*-
"""
database.py — SQLAlchemy engine, session factory, and declarative base.

URL priority (first match wins):
  1. DATABASE_URL env var     — set by Render / production host
  2. DTX_DATABASE_URL env var — legacy local-dev name (backward compat)
  3. sqlite:///./dtx.db       — zero-config local / Render free-tier fallback

Test URI : sqlite:///:memory:  (injected via override_get_db in conftest)

The module exposes:
  engine         — SQLAlchemy Engine
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

# Priority: DATABASE_URL (Render / any host) → DTX_DATABASE_URL (legacy local)
# → SQLite file fallback (zero external dependency, works on Render free tier).
DATABASE_URL: str = (
    os.getenv("DATABASE_URL")
    or os.getenv("DTX_DATABASE_URL")
    or "sqlite:///./dtx.db"
)

# Normalise legacy Heroku/Render postgres:// scheme → postgresql://
# SQLAlchemy 1.4+ requires the "postgresql" dialect prefix.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

# SQLite requires check_same_thread=False so FastAPI's thread-pool workers
# can share a connection.  PostgreSQL (and other servers) must NOT receive
# this argument — omit it entirely for non-SQLite drivers.
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
