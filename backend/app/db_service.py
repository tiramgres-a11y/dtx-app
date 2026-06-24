# -*- coding: utf-8 -*-
"""
db_service.py — Database CRUD service layer.

Replaces all mock_state.json read/write operations with transactional
SQLAlchemy calls.  Every function accepts a Session as its first argument;
commit/rollback is the caller's responsibility (handled by get_db dependency
or an explicit transaction block in tests).

Functions mirror the previous JSON helpers in main.py, sos.py, and scheduler.py
so that the refactor is a drop-in replacement at the call site.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import (
    DailyMetrics,
    ImageCache,
    MentorMessage,
    MorningQueueEntry,
    NotificationLog,
    SOSEvent,
    UserState,
)


# ---------------------------------------------------------------------------
# UserState helpers
# ---------------------------------------------------------------------------


def get_user_state(db: Session, user_id: str) -> UserState | None:
    """Return the UserState row for user_id, or None if not found."""
    return db.get(UserState, user_id)


def get_or_create_user(db: Session, user_id: str) -> UserState:
    """
    Return existing UserState or create a new one with defaults.
    Does NOT commit — caller commits via get_db() or explicit transaction.
    """
    user = db.get(UserState, user_id)
    if user is None:
        user = UserState(user_id=user_id)
        db.add(user)
        db.flush()   # assign any DB-generated defaults without committing
    return user


def get_baseline_rhr(db: Session, user_id: str) -> int | None:
    """
    Look up a user's personal baseline resting HR.
    Returns None if user not found or no baseline stored.
    Replaces main.py::_get_baseline_rhr().
    """
    user = db.get(UserState, user_id)
    if user is not None and user.baseline_rhr is not None:
        return user.baseline_rhr
    return None


def upsert_baseline_rhr(db: Session, user_id: str, baseline_rhr: int) -> UserState:
    """
    Store / update a user's baseline RHR.
    Creates the UserState row if it doesn't exist.
    Replaces main.py::_upsert_baseline_rhr().
    """
    user = get_or_create_user(db, user_id)
    user.baseline_rhr = baseline_rhr
    db.flush()
    return user


def compute_current_week(program_start_date: str | None) -> int:
    """
    Derive the current program week (1–13) from the start date (YYYY-MM-DD).
    Day 0–6 → week 1, day 7–13 → week 2, … capped at week 13.
    Returns 1 when no start date is set or the value is malformed.
    """
    if not program_start_date:
        return 1
    try:
        start = date.fromisoformat(program_start_date)
    except (ValueError, TypeError):
        return 1
    delta_days = (date.today() - start).days
    week = delta_days // 7 + 1
    return max(1, min(13, week))


def compute_program_day(program_start_date: str | None) -> int:
    """
    Derive the absolute program day (1–91) from the start date.
    Start day itself is day 1. Returns 1 when unset/malformed; capped at 91.
    """
    if not program_start_date:
        return 1
    try:
        start = date.fromisoformat(program_start_date)
    except (ValueError, TypeError):
        return 1
    delta_days = (date.today() - start).days
    return max(1, min(91, delta_days + 1))


def set_program_start_date(db: Session, user_id: str, start_date: str) -> UserState:
    """
    Store the program start date and snapshot the computed current week.
    Creates the UserState row if it doesn't exist.
    """
    user = get_or_create_user(db, user_id)
    user.program_start_date = start_date
    user.current_week = compute_current_week(start_date)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# SOS Event helpers
# ---------------------------------------------------------------------------


def append_sos_event(
    db: Session,
    user_id: str,
    week_context: int,
    timestamp_utc: str,
) -> SOSEvent:
    """
    Insert a new SOS trigger event (append-only).
    Replaces sos.py::_append_sos_event().
    """
    event = SOSEvent(
        user_id=user_id,
        week_context=week_context,
        timestamp_utc=timestamp_utc,
    )
    db.add(event)
    db.flush()   # get the auto-generated id without committing
    return event


def resolve_sos_event(
    db: Session,
    user_id: str,
    event_timestamp_utc: str,
    resolution_status: str,
    resolved_at_utc: str,
) -> bool:
    """
    Locate a SOS event by (user_id, timestamp_utc) and set resolution fields.
    Returns True if a matching unresolved event was found, False otherwise.
    Invariant: existing columns never overwritten — only null columns set.
    Replaces sos.py::_resolve_sos_event().

    Lookup strategy (in order):
      1. Exact match on (user_id, timestamp_utc) — happy path.
      2. Fallback: latest unresolved event for user_id — handles the case where
         the frontend sent a client-generated timestamp instead of the server's
         (e.g. when res.event_timestamp_utc was undefined and JS fell back to
         new Date().toISOString()).
    """
    # --- Strategy 1: exact timestamp match ---
    stmt = (
        select(SOSEvent)
        .where(SOSEvent.user_id == user_id)
        .where(SOSEvent.timestamp_utc == event_timestamp_utc)
        .where(SOSEvent.resolution_status.is_(None))
    )
    event: SOSEvent | None = db.scalars(stmt).first()

    # --- Strategy 2: latest unresolved event for this user (fallback) ---
    if event is None:
        fallback_stmt = (
            select(SOSEvent)
            .where(SOSEvent.user_id == user_id)
            .where(SOSEvent.resolution_status.is_(None))
            .order_by(SOSEvent.id.desc())
            .limit(1)
        )
        event = db.scalars(fallback_stmt).first()

    if event is None:
        return False

    event.resolution_status = resolution_status
    event.resolved_at_utc   = resolved_at_utc
    db.flush()
    return True


# ---------------------------------------------------------------------------
# Morning Queue helpers
# ---------------------------------------------------------------------------


def queue_morning_payload(
    db: Session,
    user_id: str,
    header_he: str,
    oars_affirmation_he: str,
    habit_reset_he: str,
    queued_at_utc: str,
) -> MorningQueueEntry:
    """
    Append a morning intervention payload for delivery at the next session.
    Replaces sos.py::_queue_morning_payload().
    """
    entry = MorningQueueEntry(
        user_id=user_id,
        header_he=header_he,
        oars_affirmation_he=oars_affirmation_he,
        habit_reset_he=habit_reset_he,
        queued_at_utc=queued_at_utc,
    )
    db.add(entry)
    db.flush()
    return entry


def get_morning_queue(db: Session, user_id: str) -> list[MorningQueueEntry]:
    """Return all queued morning payloads for a user (ordered by queued_at_utc)."""
    stmt = (
        select(MorningQueueEntry)
        .where(MorningQueueEntry.user_id == user_id)
        .order_by(MorningQueueEntry.queued_at_utc)
    )
    return list(db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Scheduler helpers
# ---------------------------------------------------------------------------


def get_all_users(db: Session) -> list[UserState]:
    """Return all UserState rows — used by the scheduler to scan Phase 3 users."""
    return list(db.scalars(select(UserState)).all())


def record_notification(
    db: Session,
    notification_type: str,
    user_id: str,
    sent_at: str,
    iso_week: str,
    current_week: int,
    push_message: str,
    oars_question: str,
) -> NotificationLog:
    """
    Append a notification to the audit log.
    Replaces the inline log_entry dict written to mock_state.json in scheduler.py.
    """
    log = NotificationLog(
        notification_type=notification_type,
        user_id=user_id,
        sent_at=sent_at,
        iso_week=iso_week,
        current_week=current_week,
        push_message=push_message,
        oars_question=oars_question,
    )
    db.add(log)
    db.flush()
    return log


def update_scheduler_metadata(
    db: Session,
    user: UserState,
    iso_week: str,
    current_week: int,
    dispatched_at: str,
) -> None:
    """
    Update idempotency fields on a UserState after a notification is sent.
    Replaces the inline dict mutation in scheduler.py.
    """
    user.last_notified_iso_week  = iso_week
    user.last_notified_week      = current_week
    user.last_notified_timestamp = dispatched_at
    user.notifications_sent      = (user.notifications_sent or 0) + 1
    db.flush()


# ---------------------------------------------------------------------------
# Mentor conversation helpers
# ---------------------------------------------------------------------------


def append_mentor_message(
    db: Session,
    user_id: str,
    role: str,
    content: str,
    created_at_utc: str,
    action_url: str | None = None,
    action_label: str | None = None,
) -> MentorMessage:
    """Insert one mentor-chat message (append-only)."""
    msg = MentorMessage(
        user_id=user_id,
        role=role,
        content=content,
        action_url=action_url,
        action_label=action_label,
        created_at_utc=created_at_utc,
    )
    db.add(msg)
    db.flush()
    return msg


def get_recent_mentor_messages(
    db: Session,
    user_id: str,
    limit: int = 12,
) -> list[MentorMessage]:
    """
    Return the most recent `limit` messages for a user in CHRONOLOGICAL order
    (oldest first) — ready for LLM prompt injection and frontend rendering.
    """
    stmt = (
        select(MentorMessage)
        .where(MentorMessage.user_id == user_id)
        .order_by(MentorMessage.id.desc())
        .limit(limit)
    )
    rows = list(db.scalars(stmt).all())
    rows.reverse()
    return rows


def get_recent_sos_events(
    db: Session,
    user_id: str,
    limit: int = 3,
) -> list[SOSEvent]:
    """Most recent SOS events (newest first) — context for the mentor prompt."""
    stmt = (
        select(SOSEvent)
        .where(SOSEvent.user_id == user_id)
        .order_by(SOSEvent.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Daily metrics helpers (wearable data persistence)
# ---------------------------------------------------------------------------


def upsert_daily_metrics(
    db: Session,
    user_id: str,
    metric_date: str,
    synced_at_utc: str,
    sleep_hours: float | None = None,
    steps: int | None = None,
    idle_minutes: int | None = None,
    resting_hr: int | None = None,
) -> DailyMetrics:
    """
    Insert or update the metrics row for (user_id, metric_date).
    Newest sync wins; only non-None fields overwrite existing values, so a
    partial sync (e.g. steps only) never wipes a previously stored sleep value.
    """
    stmt = (
        select(DailyMetrics)
        .where(DailyMetrics.user_id == user_id)
        .where(DailyMetrics.metric_date == metric_date)
    )
    row: DailyMetrics | None = db.scalars(stmt).first()

    if row is None:
        row = DailyMetrics(
            user_id=user_id,
            metric_date=metric_date,
            synced_at_utc=synced_at_utc,
        )
        db.add(row)

    if sleep_hours is not None:
        row.sleep_hours = sleep_hours
    if steps is not None:
        row.steps = steps
    if idle_minutes is not None:
        row.idle_minutes = idle_minutes
    if resting_hr is not None:
        row.resting_hr = resting_hr
    row.synced_at_utc = synced_at_utc

    db.flush()
    return row


def get_recent_daily_metrics(
    db: Session,
    user_id: str,
    limit: int = 7,
) -> list[DailyMetrics]:
    """
    Return the most recent `limit` daily-metrics rows for a user, in
    chronological order (oldest first) — ready for weekly aggregation.
    """
    stmt = (
        select(DailyMetrics)
        .where(DailyMetrics.user_id == user_id)
        .order_by(DailyMetrics.metric_date.desc(), DailyMetrics.id.desc())
        .limit(limit)
    )
    rows = list(db.scalars(stmt).all())
    rows.reverse()
    return rows


def get_latest_metrics(db: Session, user_id: str) -> DailyMetrics | None:
    """
    Return the most recently dated metrics row for a user, or None.
    Ordered by metric_date (string YYYY-MM-DD sorts chronologically), then id.
    """
    stmt = (
        select(DailyMetrics)
        .where(DailyMetrics.user_id == user_id)
        .order_by(DailyMetrics.metric_date.desc(), DailyMetrics.id.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


# ---------------------------------------------------------------------------
# Image cache helpers
# ---------------------------------------------------------------------------


def get_cached_image(db: Session, query: str) -> ImageCache | None:
    """Return the cached image for a query, or None."""
    return db.get(ImageCache, query)


def set_cached_image(
    db: Session,
    query: str,
    image_url: str,
    photographer: str | None,
    photographer_url: str | None,
    fetched_at_utc: str,
) -> ImageCache:
    """Insert or update the cached image for a query."""
    row = db.get(ImageCache, query)
    if row is None:
        row = ImageCache(query=query)
        db.add(row)
    row.image_url        = image_url
    row.photographer     = photographer
    row.photographer_url = photographer_url
    row.fetched_at_utc   = fetched_at_utc
    db.flush()
    return row
