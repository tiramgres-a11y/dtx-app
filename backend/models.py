# -*- coding: utf-8 -*-
"""
models.py — SQLAlchemy ORM models for the DTx backend.

Tables:
  user_states       — per-user program state (week, prep, baseline RHR, scheduler)
  sos_events        — SOS craving trigger events (append-only, resolution appended)
  morning_queue     — LAPSE intervention payloads queued for next session
  notifications_log — audit trail for all scheduler-dispatched push notifications

Design constraints (per ROADMAP.md):
  • Append-only for sos_events (no UPDATE/DELETE — resolution is a new column set)
  • All text fields in Hebrew (UTF-8) — no encoding conversion needed in Postgres/SQLite
  • Atomic writes enforced at the Session level in database.get_db()
  • No clinical logic in models — pure data persistence
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


# ---------------------------------------------------------------------------
# Helper — UTC now
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# UserState — program state per user
# ---------------------------------------------------------------------------


class UserState(Base):
    """
    One row per user_id.  Upserted on every evaluation or baseline-RHR update.

    Scheduler sub-fields track idempotency for the Friday prep-reminder job:
      last_notified_iso_week — e.g. '2026-W23'
      last_notified_week     — program week at time of dispatch
      notifications_sent     — cumulative counter (audit trail)
    """

    __tablename__ = "user_states"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    current_week: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_prepped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Baseline resting heart rate (set via /api/v1/user/baseline-rhr)
    baseline_rhr: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Scheduler idempotency (Friday prep-reminder)
    last_notified_iso_week: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_notified_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_notified_timestamp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notifications_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<UserState user_id={self.user_id!r} "
            f"week={self.current_week} baseline_rhr={self.baseline_rhr}>"
        )


# ---------------------------------------------------------------------------
# SOSEvent — craving toolkit trigger & resolution (append-only)
# ---------------------------------------------------------------------------


class SOSEvent(Base):
    """
    Append-only log of SOS trigger events.

    Invariant: once a row is inserted, existing columns are NEVER overwritten.
    Resolution is expressed by setting resolution_status + resolved_at_utc
    (which are nullable columns, initially NULL).

    This maps directly to mock_state.json["sos_events"].
    """

    __tablename__ = "sos_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    week_context: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_utc: Mapped[str] = mapped_column(String(64), nullable=False)

    # Resolution fields (set once by /sos/resolve — never overwritten)
    resolution_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    resolved_at_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<SOSEvent id={self.id} user_id={self.user_id!r} "
            f"ts={self.timestamp_utc!r} status={self.resolution_status!r}>"
        )


# ---------------------------------------------------------------------------
# MorningQueueEntry — LAPSE intervention queued for next session
# ---------------------------------------------------------------------------


class MorningQueueEntry(Base):
    """
    Intervention payloads queued when a SOS event is resolved as LAPSE.
    Delivered to the user at the start of their next session.

    Maps to mock_state.json["morning_queue"].
    """

    __tablename__ = "morning_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    header_he: Mapped[str] = mapped_column(Text, nullable=False)
    oars_affirmation_he: Mapped[str] = mapped_column(Text, nullable=False)
    habit_reset_he: Mapped[str] = mapped_column(Text, nullable=False)
    queued_at_utc: Mapped[str] = mapped_column(String(64), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MorningQueueEntry id={self.id} user_id={self.user_id!r}>"


# ---------------------------------------------------------------------------
# NotificationLog — scheduler dispatch audit trail
# ---------------------------------------------------------------------------


class NotificationLog(Base):
    """
    Full audit trail of every push notification dispatched by the scheduler.

    Maps to mock_state.json["notifications_log"].
    """

    __tablename__ = "notifications_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    sent_at: Mapped[str] = mapped_column(String(64), nullable=False)
    iso_week: Mapped[str] = mapped_column(String(16), nullable=False)
    current_week: Mapped[int] = mapped_column(Integer, nullable=False)
    push_message: Mapped[str] = mapped_column(Text, nullable=False)
    oars_question: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<NotificationLog id={self.id} user_id={self.user_id!r} "
            f"iso_week={self.iso_week!r}>"
        )


# ---------------------------------------------------------------------------
# MentorMessage — AI coach conversation log (append-only)
# ---------------------------------------------------------------------------


class MentorMessage(Base):
    """
    Append-only log of the mentor-chat conversation.

    One row per message; role is either 'user' or 'coach'.
    Recent rows are injected into the LLM prompt as conversation memory,
    and served to the frontend via GET /api/v1/mentor/history so the chat
    survives app restarts.
    """

    __tablename__ = "mentor_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(8), nullable=False)  # 'user' | 'coach'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    action_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_utc: Mapped[str] = mapped_column(String(64), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MentorMessage id={self.id} user_id={self.user_id!r} role={self.role!r}>"


# ---------------------------------------------------------------------------
# DailyMetrics — latest synced wearable data per user/day (upserted)
# ---------------------------------------------------------------------------


class DailyMetrics(Base):
    """
    One row per (user_id, metric_date).  Upserted on every Health Connect sync
    from the dashboard so the watch data is persisted server-side and available
    to the AI mentor's cognitive control room even when the user opens the chat
    directly (without visiting the dashboard first).

    Unlike sos_events, this table is NOT append-only — the latest sync for a
    given day overwrites that day's row (newest reading wins).
    """

    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD

    sleep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idle_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resting_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)

    synced_at_utc: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "metric_date", name="uq_daily_metrics_user_date"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DailyMetrics user_id={self.user_id!r} date={self.metric_date!r} "
            f"sleep={self.sleep_hours} steps={self.steps} rhr={self.resting_hr}>"
        )
