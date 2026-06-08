# -*- coding: utf-8 -*-
"""
weekly_summary.py — Weekly Summary Aggregator (Orchestrator)

Endpoint: POST /api/v1/engine/weekly-summary

Accepts up to 7 DailyRecord objects (one per day of the target week).
Aggregates sleep, steps, exercise, and heart-rate data, then produces:
  • Calculated averages (null-safe — missing days excluded from denominator)
  • Trend direction per metric (first-half vs second-half of week)
  • Week-specific OARS reflective closing question (Hebrew, from he.json)
  • Clinical insight bullets (Hebrew, from he.json)

Architecture invariants (per ROADMAP.md):
  • This module is owned exclusively by the Orchestrator
  • No DB writes — caller handles persistence
  • Zero clinical UI logic — data only
  • All Hebrew strings from locales/he.json — no inline literals
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.schemas import (
    ExerciseType,
    SleepSessionRecord,
    StepsRecord,
    ExerciseSessionRecord,
    HeartRateRecord,
)

# ---------------------------------------------------------------------------
# Locale loader (cached at import time)
# ---------------------------------------------------------------------------

# parents[1] = backend/  (backend/app/weekly_summary.py → backend/app → backend)
# he.json lives at backend/locales/he.json so it is included in the Docker build context.
_LOCALES_PATH = Path(__file__).resolve().parents[1] / "locales" / "he.json"


def _load_locales() -> dict[str, str]:
    with open(_LOCALES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


HE: dict[str, str] = _load_locales()


def _t(key: str, **kwargs: object) -> str:
    """Fetch a locale string and interpolate {{VAR}} placeholders."""
    raw = HE.get(key, f"[MISSING:{key}]")
    for k, v in kwargs.items():
        raw = raw.replace(f"{{{{{k}}}}}", str(v))
    return raw


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class DailyRecord(BaseModel):
    """One day's worth of health data — all fields optional (missing day = None)."""
    date: str = Field(..., description="ISO-8601 date string YYYY-MM-DD")
    sleep:      Optional[SleepSessionRecord]    = None
    steps:      Optional[StepsRecord]           = None
    exercise:   Optional[ExerciseSessionRecord] = None
    heart_rate: Optional[HeartRateRecord]       = None


class WeeklySummaryRequest(BaseModel):
    user_id:      str = Field(..., description="Opaque user identifier")
    current_week: int = Field(..., ge=1, le=13,
                              description="Program week number (1-13)")
    days: list[DailyRecord] = Field(
        ..., min_length=1, max_length=7,
        description="Daily records for the target week (1-7 days)"
    )


class WeeklyMetrics(BaseModel):
    """Aggregated statistics — None when no data was supplied for that metric."""
    days_with_data:         int
    days_supplied:          int

    avg_sleep_hours:        Optional[float] = None
    avg_steps:              Optional[float] = None
    avg_resting_hr:         Optional[float] = None

    total_strength_sessions: int = 0
    total_cardio_sessions:   int = 0
    total_exercise_minutes:  int = 0

    sleep_trend:    Optional[str] = None   # "improving" | "declining" | "stable"
    rhr_trend:      Optional[str] = None


class WeeklySummaryResponse(BaseModel):
    user_id:      str
    current_week: int
    phase_label:  str

    metrics: WeeklyMetrics

    oars_summary_he:   str
    insights_he:       list[str] = Field(default_factory=list)
    clinical_notes_he: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _safe_avg(values: list[float]) -> Optional[float]:
    """Return rounded average of non-None values; None if list is empty."""
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _trend(first_half: list[float], second_half: list[float],
           higher_is_better: bool) -> str:
    """
    Compare mean of first half vs second half of the week.
    Returns 'improving' | 'declining' | 'stable'.
    A 3% threshold prevents noise from triggering a trend.
    """
    if not first_half or not second_half:
        return "stable"
    avg1 = sum(first_half) / len(first_half)
    avg2 = sum(second_half) / len(second_half)
    if avg1 == 0:
        return "stable"
    delta = (avg2 - avg1) / avg1
    if abs(delta) < 0.03:
        return "stable"
    improved = delta > 0 if higher_is_better else delta < 0
    return "improving" if improved else "declining"


def _trend_label(metric: str, direction: str) -> str:
    """Map (metric, direction) → he.json key."""
    key_map = {
        ("sleep", "improving"): "WEEKLY_SLEEP_TREND_IMPROVING",
        ("sleep", "declining"): "WEEKLY_SLEEP_TREND_DECLINING",
        ("sleep", "stable"):    "WEEKLY_SLEEP_TREND_STABLE",
        ("rhr",   "improving"): "WEEKLY_RHR_TREND_IMPROVING",
        ("rhr",   "declining"): "WEEKLY_RHR_TREND_DECLINING",
        ("rhr",   "stable"):    "WEEKLY_RHR_TREND_STABLE",
    }
    return _t(key_map.get((metric, direction), "WEEKLY_SLEEP_TREND_STABLE"))


def _oars_question(week: int, avg_sleep: Optional[float]) -> str:
    """Select the OARS reflective question for the given program week."""
    week_key_map = {
        5: "WEEKLY_OARS_W5",
        6: "WEEKLY_OARS_W6",
        7: "WEEKLY_OARS_W7",
        8: "WEEKLY_OARS_W8",
        9: "WEEKLY_OARS_W9",
    }
    key = week_key_map.get(week, "WEEKLY_OARS_DEFAULT")
    sleep_str = str(avg_sleep) if avg_sleep is not None else "—"
    return _t(key, avg_sleep=sleep_str)


def _insights(metrics: WeeklyMetrics) -> list[str]:
    """Generate Hebrew clinical insight bullets based on computed metrics."""
    out: list[str] = []

    # Sleep insights
    if metrics.avg_sleep_hours is not None:
        if metrics.avg_sleep_hours >= 7.0:
            out.append(_t("WEEKLY_INSIGHT_SLEEP_GOOD"))
        elif metrics.avg_sleep_hours < 6.0:
            out.append(_t("WEEKLY_INSIGHT_SLEEP_LOW"))

    # Steps insights
    if metrics.avg_steps is not None:
        if metrics.avg_steps >= 7000:
            out.append(_t("WEEKLY_INSIGHT_STEPS_GOOD"))
        elif metrics.avg_steps < 5000:
            out.append(_t("WEEKLY_INSIGHT_STEPS_LOW"))

    # Exercise insights
    total_ex = metrics.total_strength_sessions + metrics.total_cardio_sessions
    if metrics.total_strength_sessions >= 3:
        out.append(_t("WEEKLY_INSIGHT_STRENGTH_GOOD",
                      count=metrics.total_strength_sessions))
    elif total_ex == 0 and metrics.days_with_data >= 3:
        out.append(_t("WEEKLY_INSIGHT_NO_EXERCISE"))

    return out


# ---------------------------------------------------------------------------
# Core aggregation function
# ---------------------------------------------------------------------------

def aggregate_week(request: WeeklySummaryRequest) -> WeeklySummaryResponse:
    """
    Pure aggregation — no side effects, no DB writes.
    Handles missing days gracefully:
      • Null fields are excluded from averages (denominator = days with data only)
      • Division by zero is impossible by construction
    """
    days = request.days

    # ── Collect per-metric value lists (only non-null days included) ────────
    sleep_values:  list[float] = []
    steps_values:  list[float] = []
    rhr_values:    list[float] = []

    strength_count = 0
    cardio_count   = 0
    exercise_mins  = 0
    days_with_data = 0

    for day in days:
        day_has_any = False

        if day.sleep is not None:
            sleep_values.append(day.sleep.duration_hours)
            day_has_any = True

        if day.steps is not None:
            steps_values.append(float(day.steps.steps))
            day_has_any = True

        if day.heart_rate is not None:
            rhr_values.append(float(day.heart_rate.resting_hr))
            day_has_any = True

        if day.exercise is not None:
            day_has_any = True
            if day.exercise.completed:
                exercise_mins += day.exercise.duration_minutes
                if day.exercise.type == ExerciseType.STRENGTH:
                    strength_count += 1
                elif day.exercise.type == ExerciseType.CARDIO:
                    cardio_count += 1

        if day_has_any:
            days_with_data += 1

    # ── Trend calculation (split week in half) ──────────────────────────────
    mid = len(sleep_values) // 2
    sleep_trend_dir = _trend(sleep_values[:mid], sleep_values[mid:],
                              higher_is_better=True)
    rhr_trend_dir   = _trend(rhr_values[:len(rhr_values)//2],
                              rhr_values[len(rhr_values)//2:],
                              higher_is_better=False)  # lower RHR = better

    # ── Build metrics object ────────────────────────────────────────────────
    metrics = WeeklyMetrics(
        days_with_data=days_with_data,
        days_supplied=len(days),
        avg_sleep_hours=_safe_avg(sleep_values),
        avg_steps=_safe_avg(steps_values),
        avg_resting_hr=_safe_avg(rhr_values),
        total_strength_sessions=strength_count,
        total_cardio_sessions=cardio_count,
        total_exercise_minutes=exercise_mins,
        sleep_trend=_trend_label("sleep", sleep_trend_dir) if sleep_values else None,
        rhr_trend=_trend_label("rhr",   rhr_trend_dir)   if rhr_values  else None,
    )

    # ── OARS question and insights ──────────────────────────────────────────
    oars_q   = _oars_question(request.current_week, metrics.avg_sleep_hours)
    insights = _insights(metrics)

    # ── Phase label ─────────────────────────────────────────────────────────
    if request.current_week <= 4:
        phase_label = "שלב 1 — איפוס (שבועות 1–4)"
    elif request.current_week <= 9:
        phase_label = "שלב 2 — עומס (שבועות 5–9)"
    else:
        phase_label = f"שלב — שבוע {request.current_week}"

    return WeeklySummaryResponse(
        user_id=request.user_id,
        current_week=request.current_week,
        phase_label=phase_label,
        metrics=metrics,
        oars_summary_he=oars_q,
        insights_he=insights,
        clinical_notes_he=[_t("WEEKLY_CLINICAL_NOTE")],
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/engine", tags=["Weekly Summary"])


@router.post("/weekly-summary", response_model=WeeklySummaryResponse)
async def weekly_summary(request: WeeklySummaryRequest) -> WeeklySummaryResponse:
    """
    Weekly Summary Aggregator endpoint.

    Accepts 1–7 DailyRecord objects covering a single program week.
    Returns aggregated metrics, trends, an OARS reflective question,
    and clinical insights — all in Hebrew.

    Does NOT modify any existing daily endpoint; runs purely on the
    supplied batch of records.
    """
    return aggregate_week(request)
