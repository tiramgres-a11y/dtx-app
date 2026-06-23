# -*- coding: utf-8 -*-
"""
DTx Backend — Orchestrator (Rules Engine)
FastAPI application entry point. v0.7.0

Phase 1  : clinical evaluation — Weeks 1–4 (Reset).
Phase 2  : Weeks 5–9 (Overload) — GLUT4 + Bio-feedback / Recovery rules.
Phase 3  : Weeks 10–13 (Maintenance & Modularity).
SOS      : Weeks 11–12 crisis toolkit.
Scheduler: Friday 12:00 prep reminder (Phase 3).

v0.7.0 changes:
  - Replaced mock_state.json persistence with SQLAlchemy / PostgreSQL.
  - All state reads/writes use db_service.py via DB Session dependency.
  - Backward-compatible: API contracts unchanged; frontend requires no changes.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.database import Base, engine, get_db
from backend.app.schemas import EvaluationRequest, EvaluationResponse, HealthMetricsRequest
from backend.app.rules import evaluate_phase1, PHASE_1_WEEKS
from backend.app.rules_phase2 import evaluate_phase2, PHASE_2_WEEKS
from backend.app.rules_phase3 import evaluate_phase3, PHASE_3_WEEKS
from backend.app.sos import router as sos_router
from backend.app.weekly_summary import router as weekly_summary_router
from backend.app.scheduler import (
    create_scheduler,
    start_scheduler,
    shutdown_scheduler,
    get_scheduler,
)
from backend.app import db_service
from backend.llm_router import MentorChatRequest, MentorResponse, get_mentor_response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Create all tables on startup (idempotent — only creates missing tables)
# ---------------------------------------------------------------------------

def _init_db() -> None:
    """Create all SQLAlchemy-mapped tables if they don't already exist."""
    # Import models so Base.metadata knows about them
    import backend.models  # noqa: F401
    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# FastAPI lifespan — DB init + scheduler
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    _init_db()
    create_scheduler()
    start_scheduler()
    logger.info("DTx Orchestrator v0.7.0 started — DB initialised, scheduler running.")
    yield
    shutdown_scheduler()
    logger.info("DTx Orchestrator shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    lifespan=lifespan,
    title="DTx Orchestrator — Clinical Rules Engine",
    description=(
        "Backend rules engine for the diabetes prevention DTx app. "
        "Phase 1: Reset (Weeks 1–4). "
        "Phase 2: Overload (Weeks 5–9). "
        "Phase 3: Maintenance & Modularity (Weeks 10–13). "
        "SOS Toolkit: Weeks 11–12. "
        "Proactive Scheduler: Friday 12:00 prep reminder. "
        "v0.7.0: PostgreSQL persistence via SQLAlchemy."
    ),
    version="0.7.0",
)

app.include_router(sos_router)
app.include_router(weekly_summary_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check() -> dict:
    sched = get_scheduler()
    return {
        "status":    "ok",
        "phases":    "Phase 1 (Weeks 1–4) | Phase 2 (Weeks 5–9) | Phase 3 (Weeks 10–13)",
        "version":   "0.7.0",
        "scheduler": "running" if (sched and sched.running) else "stopped",
        "db":        "postgresql (SQLAlchemy)",
    }


@app.get("/api/v1/scheduler/status")
async def scheduler_status() -> dict:
    sched = get_scheduler()
    if not sched or not sched.running:
        return {"running": False, "jobs": []}
    jobs = [
        {
            "id":       job.id,
            "name":     job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        }
        for job in sched.get_jobs()
    ]
    return {"running": True, "jobs": jobs}


@app.post("/api/v1/evaluate", response_model=EvaluationResponse)
async def evaluate(
    request: EvaluationRequest,
    db: Session = Depends(get_db),
) -> EvaluationResponse:
    """
    Main Orchestrator evaluation endpoint.

    Routes to the correct phase engine based on current_week:
      1–4  → Phase 1 (Reset)
      5–9  → Phase 2 (Overload)
      10–13→ Phase 3 (Maintenance & Modularity)
      14+  → 501 Not Implemented

    For Phase 2/3: auto-injects the stored baseline RHR when not supplied.
    """
    if request.current_week in PHASE_1_WEEKS:
        return evaluate_phase1(request)

    if request.current_week in PHASE_2_WEEKS:
        if request.user_baseline_rhr is None and request.heart_rate is not None:
            stored = db_service.get_baseline_rhr(db, request.user_id)
            if stored is not None:
                request = request.model_copy(update={"user_baseline_rhr": stored})
        return evaluate_phase2(request)

    if request.current_week in PHASE_3_WEEKS:
        if request.user_baseline_rhr is None and request.heart_rate is not None:
            stored = db_service.get_baseline_rhr(db, request.user_id)
            if stored is not None:
                request = request.model_copy(update={"user_baseline_rhr": stored})
        return evaluate_phase3(request)

    raise HTTPException(
        status_code=501,
        detail=(
            f"שבוע {request.current_week} חורג מטווח התוכנית (שבועות 1–13). "
            "אנא בדוק את שבוע התוכנית הנוכחי שלך."
        ),
    )


@app.post("/api/v1/mentor/chat", response_model=MentorResponse)
async def mentor_chat(
    request: MentorChatRequest,
    db: Session = Depends(get_db),
) -> MentorResponse:
    """
    AI Mentor Coach — powered by Claude (LLM Router) v3.

    Cognitive control room: the prompt receives conversation memory
    (last 12 messages from mentor_messages) + recent SOS events + the user's
    DB-stored programme state, so responses are context-aware and the dialogue
    continues across requests and app restarts.

    Both the user message and the coach reply are persisted (append-only).

    Requires ANTHROPIC_API_KEY to be set in backend/.env.
    """
    physiological_data = {
        k: v for k, v in {
            "sleep_hours":   request.sleep_hours,
            "steps":         request.steps,
            "resting_hr":    request.resting_hr,
            "baseline_rhr":  request.baseline_rhr,
        }.items()
        if v is not None
    }

    # Context loading + persistence are best-effort: conversation memory is an
    # enhancement — a DB hiccup must never block the AI response itself.
    history: list = []
    sos_context: list = []
    try:
        # Fill baseline RHR from DB when the client didn't send one
        if "baseline_rhr" not in physiological_data:
            db_baseline = db_service.get_baseline_rhr(db, request.user_id)
            if db_baseline is not None:
                physiological_data["baseline_rhr"] = db_baseline

        # Fill latest wearable metrics from DB for any field the client omitted,
        # so the mentor sees the watch data even when the chat is opened directly
        # (without visiting the dashboard first this session).
        latest = db_service.get_latest_metrics(db, request.user_id)
        if latest is not None:
            if "sleep_hours" not in physiological_data and latest.sleep_hours is not None:
                physiological_data["sleep_hours"] = latest.sleep_hours
            if "steps" not in physiological_data and latest.steps is not None:
                physiological_data["steps"] = latest.steps
            if "resting_hr" not in physiological_data and latest.resting_hr is not None:
                physiological_data["resting_hr"] = latest.resting_hr

        # Conversation memory — loaded BEFORE persisting the new user message
        history = [
            {"role": m.role, "content": m.content}
            for m in db_service.get_recent_mentor_messages(db, request.user_id, limit=12)
        ]

        # Recent SOS events as physiological/behavioural context
        sos_context = [
            {
                "timestamp_utc":     ev.timestamp_utc,
                "resolution_status": ev.resolution_status,
            }
            for ev in db_service.get_recent_sos_events(db, request.user_id, limit=3)
        ]

        if request.free_text:
            db_service.append_mentor_message(
                db=db,
                user_id=request.user_id,
                role="user",
                content=request.free_text,
                created_at_utc=datetime.now(timezone.utc).isoformat(),
            )
    except Exception as exc:
        logger.warning("mentor_chat: context load failed — continuing without memory. %s", exc)
        db.rollback()
        history, sos_context = [], []

    try:
        response = get_mentor_response(
            physiological_data=physiological_data,
            dtx_week=request.current_week,
            free_text=request.free_text,
            history=history,
            sos_context=sos_context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("mentor_chat error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="שגיאה בתקשורת עם שירות ה-AI. אנא נסה שוב מאוחר יותר.",
        ) from exc

    try:
        db_service.append_mentor_message(
            db=db,
            user_id=request.user_id,
            role="coach",
            content=response.mentor_text,
            action_url=response.action_url,
            action_label=response.action_label,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        # get_db() commits on successful return
    except Exception as exc:
        logger.warning("mentor_chat: failed to persist coach reply. %s", exc)
        db.rollback()

    return response


@app.get("/api/v1/mentor/history")
async def mentor_history(
    user_id: str,
    limit: int = 30,
    db: Session = Depends(get_db),
) -> dict:
    """
    Conversation history for the Coach chat screen — chronological order.
    Lets the frontend restore the dialogue after app restarts.
    """
    try:
        messages = db_service.get_recent_mentor_messages(db, user_id, limit=limit)
    except Exception as exc:
        logger.warning("mentor_history: load failed — returning empty. %s", exc)
        db.rollback()
        messages = []
    return {
        "user_id": user_id,
        "messages": [
            {
                "role":          m.role,
                "content":       m.content,
                "action_url":    m.action_url,
                "action_label":  m.action_label,
                "created_at_utc": m.created_at_utc,
            }
            for m in messages
        ],
    }


@app.post("/api/v1/health/metrics")
async def save_health_metrics(
    request: HealthMetricsRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Persist the latest wearable metrics from a dashboard Health Connect sync.
    Upserts the (user_id, metric_date) row so the AI mentor can read it later.
    """
    metric_date = request.metric_date or datetime.now(timezone.utc).date().isoformat()
    row = db_service.upsert_daily_metrics(
        db=db,
        user_id=request.user_id,
        metric_date=metric_date,
        synced_at_utc=datetime.now(timezone.utc).isoformat(),
        sleep_hours=request.sleep_hours,
        steps=request.steps,
        idle_minutes=request.idle_minutes,
        resting_hr=request.resting_hr,
    )
    # get_db() commits on successful return
    return {
        "user_id":      request.user_id,
        "metric_date":  metric_date,
        "stored":       True,
        "sleep_hours":  row.sleep_hours,
        "steps":        row.steps,
        "idle_minutes": row.idle_minutes,
        "resting_hr":   row.resting_hr,
    }


@app.get("/api/v1/health/metrics")
async def get_health_metrics(
    user_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Return the latest stored wearable metrics for a user (or nulls)."""
    latest = db_service.get_latest_metrics(db, user_id)
    if latest is None:
        return {"user_id": user_id, "has_data": False}
    return {
        "user_id":       user_id,
        "has_data":      True,
        "metric_date":   latest.metric_date,
        "sleep_hours":   latest.sleep_hours,
        "steps":         latest.steps,
        "idle_minutes":  latest.idle_minutes,
        "resting_hr":    latest.resting_hr,
        "synced_at_utc": latest.synced_at_utc,
    }


@app.post("/api/v1/user/baseline-rhr")
async def set_baseline_rhr(
    user_id: str,
    baseline_rhr: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Store a user's personal baseline resting HR.
    Called during onboarding or after a calm-state measurement.
    """
    if not (20 <= baseline_rhr <= 250):
        raise HTTPException(status_code=422, detail="baseline_rhr must be 20–250 BPM")
    db_service.upsert_baseline_rhr(db, user_id, baseline_rhr)
    # get_db() commits on return — no explicit commit needed here
    return {"user_id": user_id, "baseline_rhr": baseline_rhr, "stored": True}
