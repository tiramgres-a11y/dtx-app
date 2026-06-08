# -*- coding: utf-8 -*-
"""
test_scheduler.py — Tests for the Friday prep-reminder scheduler job.

All tests call check_weekend_prep_status() directly with:
  * A controlled `now` datetime (Friday, various times)
  * A spy `dispatch_fn` to capture push calls
  * `db_session_factory` wired to the in-memory SQLite test DB

No real APScheduler is started — the job logic is tested in isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app import db_service
from backend.app.scheduler import check_weekend_prep_status, PHASE_3_MIN_WEEK


# Friday noon UTC (2026-01-02 is a Friday)
_FRIDAY_NOON = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
_FRIDAY_NOON_WEEK = "2026-W01"


def _spy():
    calls = []
    def fn(user_id, message, oars_question):
        calls.append({"user_id": user_id, "msg": message, "oars": oars_question})
    fn.calls = calls
    return fn


# ---------------------------------------------------------------------------
# No users → empty results
# ---------------------------------------------------------------------------


def test_no_users_returns_empty(db, db_session_factory):
    results = check_weekend_prep_status(
        now=_FRIDAY_NOON,
        dispatch_fn=_spy(),
        db_session_factory=db_session_factory,
    )
    assert results == []


# ---------------------------------------------------------------------------
# Phase 1/2 user skipped
# ---------------------------------------------------------------------------


def test_phase1_user_skipped(db, db_session_factory):
    user = db_service.get_or_create_user(db, "phase1-user")
    user.current_week = 3
    db.commit()

    spy = _spy()
    results = check_weekend_prep_status(
        now=_FRIDAY_NOON,
        dispatch_fn=spy,
        db_session_factory=db_session_factory,
    )
    assert results[0]["action"] == "skipped_not_phase3"
    assert len(spy.calls) == 0


# ---------------------------------------------------------------------------
# Phase 3, already prepped → skipped
# ---------------------------------------------------------------------------


def test_phase3_prepped_user_skipped(db, db_session_factory):
    user = db_service.get_or_create_user(db, "prepped-user")
    user.current_week = 10
    user.is_prepped = True
    db.commit()

    spy = _spy()
    results = check_weekend_prep_status(
        now=_FRIDAY_NOON,
        dispatch_fn=spy,
        db_session_factory=db_session_factory,
    )
    assert results[0]["action"] == "skipped_prepped"
    assert len(spy.calls) == 0


# ---------------------------------------------------------------------------
# Phase 3, not prepped → push sent + DB updated
# ---------------------------------------------------------------------------


def test_phase3_not_prepped_sends_push(db, db_session_factory):
    user = db_service.get_or_create_user(db, "needs-push")
    user.current_week = 10
    user.is_prepped = False
    db.commit()

    spy = _spy()
    results = check_weekend_prep_status(
        now=_FRIDAY_NOON,
        dispatch_fn=spy,
        db_session_factory=db_session_factory,
    )
    assert results[0]["action"] == "sent"
    assert len(spy.calls) == 1
    assert spy.calls[0]["user_id"] == "needs-push"


def test_push_updates_db_idempotency_field(db, db_session_factory):
    user = db_service.get_or_create_user(db, "idem-user")
    user.current_week = 11
    user.is_prepped = False
    db.commit()

    check_weekend_prep_status(
        now=_FRIDAY_NOON,
        dispatch_fn=_spy(),
        db_session_factory=db_session_factory,
    )

    # Refresh from DB
    db.expire(user)
    assert user.last_notified_iso_week == _FRIDAY_NOON_WEEK
    assert user.notifications_sent == 1


# ---------------------------------------------------------------------------
# Idempotency: same ISO week → no duplicate push
# ---------------------------------------------------------------------------


def test_idempotency_no_duplicate_push(db, db_session_factory):
    user = db_service.get_or_create_user(db, "idem-dup-user")
    user.current_week = 12
    user.is_prepped = False
    user.last_notified_iso_week = _FRIDAY_NOON_WEEK  # already notified this week
    db.commit()

    spy = _spy()
    results = check_weekend_prep_status(
        now=_FRIDAY_NOON,
        dispatch_fn=spy,
        db_session_factory=db_session_factory,
    )
    assert results[0]["action"] == "skipped_idempotent"
    assert len(spy.calls) == 0


# ---------------------------------------------------------------------------
# Multiple users — mixed results
# ---------------------------------------------------------------------------


def test_multiple_users_mixed(db, db_session_factory):
    u1 = db_service.get_or_create_user(db, "multi-a")
    u1.current_week = 10
    u1.is_prepped = False

    u2 = db_service.get_or_create_user(db, "multi-b")
    u2.current_week = 5   # Phase 2 — skip

    u3 = db_service.get_or_create_user(db, "multi-c")
    u3.current_week = 13
    u3.is_prepped = True  # skip

    db.commit()

    spy = _spy()
    results = check_weekend_prep_status(
        now=_FRIDAY_NOON,
        dispatch_fn=spy,
        db_session_factory=db_session_factory,
    )
    actions = {r["user_id"]: r["action"] for r in results}
    assert actions["multi-a"] == "sent"
    assert actions["multi-b"] == "skipped_not_phase3"
    assert actions["multi-c"] == "skipped_prepped"
    assert len(spy.calls) == 1
