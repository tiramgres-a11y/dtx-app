# -*- coding: utf-8 -*-
"""
scheduler.py — Proactive Background Task Scheduler (Phase 3)

v0.7.0: Replaced mock_state.json with SQLAlchemy DB Session.
The scheduler creates its own Session (not via Depends, since it runs outside
request context) and commits/rolls back atomically per user.

Registered cron job:
  check_weekend_prep_status
    Schedule : Every Friday at 12:00 (noon) Asia/Jerusalem
    Logic    : Scan all UserState rows for Phase 3 users (current_week >= 10)
               who have is_prepped=False and have NOT been notified this
               ISO calendar week (idempotency via last_notified_iso_week).

Idempotency contract:
  UserState.last_notified_iso_week is set after each successful dispatch.
  This value is persisted to the DB, so server restarts are safe.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron       import CronTrigger

from backend.database import SessionLocal
from backend.app import db_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Locale loader
# ---------------------------------------------------------------------------

# parents[1] = backend/  (backend/app/scheduler.py → backend/app → backend)
# he.json lives at backend/locales/he.json so it is included in the Docker build context.
_ROOT         = Path(__file__).resolve().parents[1]
_LOCALES_PATH = _ROOT / "locales" / "he.json"


def _load_locales() -> dict[str, str]:
    with open(_LOCALES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


_HE: dict[str, str] = _load_locales()


def _t(key: str) -> str:
    return _HE.get(key, f"[MISSING:{key}]")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PHASE_3_MIN_WEEK: int = 10
CRON_HOUR:        int = 12
CRON_MINUTE:      int = 0
CRON_DAY_OF_WEEK: str = "fri"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso_week(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


# ---------------------------------------------------------------------------
# Mock push dispatcher
# ---------------------------------------------------------------------------


def _dispatch_push(user_id: str, message: str, oars_question: str) -> None:
    logger.info(
        "PUSH_DISPATCH user_id=%s message=%r oars=%r",
        user_id, message[:40], oars_question[:40],
    )
    print(
        f"[PUSH] user={user_id} | "
        f"msg={message[:50]}... | "
        f"oars={oars_question[:50]}..."
    )


# ---------------------------------------------------------------------------
# Core job logic — injectable for testing
# ---------------------------------------------------------------------------


def check_weekend_prep_status(
    now:         datetime | None = None,
    dispatch_fn: Callable        = _dispatch_push,
    db_session_factory: Callable = SessionLocal,
) -> list[dict]:
    """
    Scan all UserState rows and send Friday prep-reminder pushes.

    Parameters
    ----------
    now                 : override current datetime (for tests).
    dispatch_fn         : push function (spy in tests).
    db_session_factory  : callable that returns a Session (override in tests).

    Returns list of result dicts per user.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    current_iso_week = _iso_week(now.date())
    results: list[dict] = []

    db = db_session_factory()
    try:
        users = db_service.get_all_users(db)

        for user in users:
            user_id      = user.user_id
            current_week = user.current_week

            # Gate 1: must be Phase 3
            if current_week < PHASE_3_MIN_WEEK:
                results.append({
                    "user_id": user_id,
                    "action":  "skipped_not_phase3",
                    "reason":  _t("SCHEDULER_LOG_NOT_PHASE3"),
                })
                continue

            # Gate 2: must not already be prepped
            if user.is_prepped:
                results.append({
                    "user_id": user_id,
                    "action":  "skipped_prepped",
                    "reason":  _t("SCHEDULER_LOG_SKIPPED_PREPPED"),
                })
                continue

            # Gate 3: idempotency
            if user.last_notified_iso_week == current_iso_week:
                results.append({
                    "user_id": user_id,
                    "action":  "skipped_idempotent",
                    "reason":  _t("SCHEDULER_LOG_SKIPPED_IDEMPOTENT"),
                })
                continue

            # All gates passed — dispatch and record atomically
            push_msg      = _t("SCHEDULER_PREP_PUSH")
            oars_q        = _t("SCHEDULER_PREP_OARS")
            dispatched_at = now.isoformat()

            dispatch_fn(user_id, push_msg, oars_q)

            db_service.update_scheduler_metadata(
                db=db,
                user=user,
                iso_week=current_iso_week,
                current_week=current_week,
                dispatched_at=dispatched_at,
            )
            db_service.record_notification(
                db=db,
                notification_type="WEEKEND_PREP_REMINDER",
                user_id=user_id,
                sent_at=dispatched_at,
                iso_week=current_iso_week,
                current_week=current_week,
                push_message=push_msg,
                oars_question=oars_q,
            )

            results.append({
                "user_id":       user_id,
                "action":        "sent",
                "reason":        _t("SCHEDULER_LOG_SENT"),
                "iso_week":      current_iso_week,
                "dispatched_at": dispatched_at,
                "push_message":  push_msg,
                "oars_question": oars_q,
            })

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    logger.info("check_weekend_prep_status completed: %d results", len(results))
    return results


# ---------------------------------------------------------------------------
# APScheduler setup
# ---------------------------------------------------------------------------

_scheduler: AsyncIOScheduler | None = None


def create_scheduler() -> AsyncIOScheduler:
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Jerusalem")
    _scheduler.add_job(
        func             = check_weekend_prep_status,
        trigger          = CronTrigger(
            day_of_week = CRON_DAY_OF_WEEK,
            hour        = CRON_HOUR,
            minute      = CRON_MINUTE,
            timezone    = "Asia/Jerusalem",
        ),
        id               = "check_weekend_prep_status",
        name             = "Friday 12:00 — Weekend Prep Reminder (Phase 3)",
        replace_existing = True,
        misfire_grace_time = 3600,
    )
    logger.info(
        "Scheduler configured: check_weekend_prep_status → %s %s:%02d",
        CRON_DAY_OF_WEEK.upper(), CRON_HOUR, CRON_MINUTE,
    )
    return _scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


def start_scheduler() -> None:
    if _scheduler and not _scheduler.running:
        _scheduler.start()
        logger.info("Scheduler started.")


def shutdown_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down.")
