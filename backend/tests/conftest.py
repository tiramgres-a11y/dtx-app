# -*- coding: utf-8 -*-
"""
conftest.py — Shared pytest fixtures for the DTx backend test suite.

Critical: DTX_DATABASE_URL is set to an in-memory SQLite URI at the very top,
BEFORE any backend module is imported. This ensures that backend.database.engine
is created against SQLite, not PostgreSQL — so tests run without a live DB server.

Test isolation:
  * Tables are created once (pytest_configure hook).
  * Each `db` fixture yields a Session that is rolled back after the test.
  * The `client` fixture overrides `get_db` to use the same rolled-back session.
"""

from __future__ import annotations

import os

# ── MUST be first, before ANY backend import ─────────────────────────────────
os.environ["DTX_DATABASE_URL"] = "sqlite:///:memory:"
# ─────────────────────────────────────────────────────────────────────────────

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# ---------------------------------------------------------------------------
# Shared in-memory SQLite engine
# We create our OWN engine (separate from backend.database.engine) so we can
# share a single connection across the session and roll back per-test.
# ---------------------------------------------------------------------------

_SQLITE_URL = "sqlite:///:memory:"
_engine = create_engine(
    _SQLITE_URL,
    connect_args={"check_same_thread": False},
)
_TestingSessionLocal = sessionmaker(
    bind=_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def pytest_configure(config):
    """Create all ORM tables in the shared in-memory DB before any test runs."""
    import backend.models  # noqa: F401 — registers models with Base.metadata
    from backend.database import Base
    Base.metadata.create_all(bind=_engine)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def db() -> Session:
    """
    Return a Session backed by the in-memory SQLite engine.
    Each test gets a connection with a savepoint so that all writes can be
    rolled back after the test — keeping tests isolated.
    """
    connection = _engine.connect()
    transaction = connection.begin()
    session = _TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    """
    FastAPI TestClient with `get_db` overridden to use the rolled-back test session.
    This ensures HTTP-level tests share the same in-memory DB as direct db_service tests.

    The lifespan _init_db() will run against backend.database.engine, which now
    points to SQLite (because DTX_DATABASE_URL was set above).
    """
    from backend.app.main import app
    from backend.database import get_db

    def _override_get_db():
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def db_session_factory(db: Session):
    """
    Returns a callable that yields the test DB session.
    Injected into scheduler's `db_session_factory` parameter in scheduler tests.
    The scheduler calls db_session_factory() and then db.commit()/close() — but
    in tests we want the caller to own the lifecycle, so this returns a wrapper
    that skips the close so the test can still inspect the session state.
    """
    class _NoCloseSession:
        """Proxy that suppresses close() so the test fixture still owns the session."""
        def __init__(self, session: Session):
            self._s = session

        def __getattr__(self, name):
            return getattr(self._s, name)

        def close(self):
            pass  # no-op — the db fixture manages lifecycle

    def _factory():
        return _NoCloseSession(db)

    return _factory
