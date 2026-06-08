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

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.database import Base, engine, get_db
from backend.app.schemas import EvaluationRequest, EvaluationResponse
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
async def mentor_chat(request: MentorChatRequest) -> MentorResponse:
    """
    AI Mentor Coach — powered by Claude (LLM Router).

    Accepts physiological data (sleep, steps, HR) + DTx week and returns
    a personalised, OARS-compliant Hebrew coach message with an optional
    recipe or exercise link.

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
    try:
        return get_mentor_response(
            physiological_data=physiological_data,
            dtx_week=request.current_week,
            free_text=request.free_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("mentor_chat error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="שגיאה בתקשורת עם שירות ה-AI. אנא נסה שוב מאוחר יותר.",
        ) from exc


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
