# -*- coding: utf-8 -*-
"""
SOS Craving Toolkit — Week 11-12 Crisis Management & Resolution Engine.

v0.7.0: Replaced mock_state.json persistence with SQLAlchemy DB Session.
All Hebrew strings sourced exclusively from locales/he.json.
Past SOS events are NEVER deleted — resolution is appended via column update.

Architecture (per ROADMAP.md):
  Owned by the Orchestrator. Workers supply trigger/resolve payloads.
  Zero clinical logic in Workers — all rules and state mutations here.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.app import db_service

# ---------------------------------------------------------------------------
# Localisation
# ---------------------------------------------------------------------------

# parents[1] = backend/  (backend/app/sos.py → backend/app → backend)
# he.json lives at backend/locales/he.json so it is included in the Docker build context.
_ROOT         = Path(__file__).resolve().parents[1]
_LOCALES_PATH = _ROOT / "locales" / "he.json"


def _load_locales() -> dict[str, str]:
    with open(_LOCALES_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    required = {
        "SOS_RELAPSE_EMPATHY", "SOS_STEP1_TITLE", "SOS_STEP1_INSTRUCTION",
        "SOS_STEP2_TITLE", "SOS_STEP2_INSTRUCTION",
        "SOS_STEP3_TITLE", "SOS_STEP3_INSTRUCTION",
        "SOS_PROTOCOL_HEADER", "SOS_CLOSING_HE", "PHASE_WEEK11",
        "PHASE_WEEK12", "LAPSE_OARS_AFFIRMATION", "LAPSE_HABIT_RESET",
        "RESOLVE_SUCCESS_HE", "RESOLVE_LAPSE_ACK_HE", "MORNING_QUEUE_HEADER_HE",
    }
    missing = required - data.keys()
    if missing:
        raise RuntimeError(f"locales/he.json is missing required keys: {missing}")
    return data


HE: dict[str, str] = _load_locales()

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class SOSTriggerRequest(BaseModel):
    user_id: str = Field(..., description="Opaque user identifier")
    week_context: int = Field(default=11, ge=1, le=13)


class SOSProtocolStep(BaseModel):
    step_number: int
    title_he: str
    instruction_he: str


class SOSTriggerResponse(BaseModel):
    user_id: str
    week_context: int
    phase_he: str
    empathy_message_he: str
    protocol_header_he: str
    protocol_steps: list[SOSProtocolStep]
    closing_message_he: str
    event_logged: bool
    timestamp_utc: str
    # event_timestamp_utc mirrors timestamp_utc so the frontend can use either
    # field name when constructing the subsequent /resolve request.
    event_timestamp_utc: str


_PROTOCOL_STEPS: list[SOSProtocolStep] = [
    SOSProtocolStep(
        step_number=1,
        title_he=HE["SOS_STEP1_TITLE"],
        instruction_he=HE["SOS_STEP1_INSTRUCTION"],
    ),
    SOSProtocolStep(
        step_number=2,
        title_he=HE["SOS_STEP2_TITLE"],
        instruction_he=HE["SOS_STEP2_INSTRUCTION"],
    ),
    SOSProtocolStep(
        step_number=3,
        title_he=HE["SOS_STEP3_TITLE"],
        instruction_he=HE["SOS_STEP3_INSTRUCTION"],
    ),
]

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/sos", tags=["SOS Craving Toolkit"])


@router.post("/trigger", response_model=SOSTriggerResponse)
async def sos_trigger(
    request: SOSTriggerRequest,
    db: Session = Depends(get_db),
) -> SOSTriggerResponse:
    """
    SOS Craving Toolkit endpoint — Week 11 Crisis Management.

    Logs the trigger event to the database and returns the 3-step Hebrew
    protocol along with an OARS empathy message sourced from locales/he.json.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        db_service.append_sos_event(
            db=db,
            user_id=request.user_id,
            week_context=request.week_context,
            timestamp_utc=timestamp,
        )
        # get_db() commits automatically on successful return
        event_logged = True
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"שגיאה בשמירת אירוע SOS: {exc}",
        ) from exc

    return SOSTriggerResponse(
        user_id=request.user_id,
        week_context=request.week_context,
        phase_he=HE["PHASE_WEEK11"],
        empathy_message_he=HE["SOS_RELAPSE_EMPATHY"],
        protocol_header_he=HE["SOS_PROTOCOL_HEADER"],
        protocol_steps=_PROTOCOL_STEPS,
        closing_message_he=HE["SOS_CLOSING_HE"],
        event_logged=event_logged,
        timestamp_utc=timestamp,
        event_timestamp_utc=timestamp,  # alias — matches frontend's res.event_timestamp_utc
    )


# ---------------------------------------------------------------------------
# Resolution schemas (Week 12)
# ---------------------------------------------------------------------------


class SOSResolutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    LAPSE   = "LAPSE"


class SOSResolveRequest(BaseModel):
    user_id: str = Field(..., description="Must match the original trigger user_id")
    event_timestamp_utc: str = Field(
        ...,
        description="ISO-8601 timestamp returned by /trigger",
    )
    status: SOSResolutionStatus
    week_context: int = Field(default=12, ge=1, le=13)


class MorningQueuePayload(BaseModel):
    oars_affirmation_he: str
    habit_reset_he: str
    header_he: str
    queued_at_utc: str


class SOSResolveResponse(BaseModel):
    user_id: str
    event_timestamp_utc: str
    status: SOSResolutionStatus
    resolved_at_utc: str
    acknowledgement_he: str
    morning_queue: MorningQueuePayload | None = None


@router.post("/resolve", response_model=SOSResolveResponse)
async def sos_resolve(
    request: SOSResolveRequest,
    db: Session = Depends(get_db),
) -> SOSResolveResponse:
    """
    SOS Resolution endpoint — Week 12 Clinical Logic.

    Closes the loop on a craving event. Appends resolution_status and
    resolved_at_utc. If status == LAPSE, queues a morning intervention.
    Past event data is never deleted or overwritten.
    """
    resolved_at = datetime.now(timezone.utc).isoformat()

    matched = db_service.resolve_sos_event(
        db=db,
        user_id=request.user_id,
        event_timestamp_utc=request.event_timestamp_utc,
        resolution_status=request.status.value,
        resolved_at_utc=resolved_at,
    )

    if not matched:
        raise HTTPException(
            status_code=404,
            detail=(
                f"לא נמצא אירוע SOS עבור המשתמש '{request.user_id}' "
                f"עם חותמת הזמן '{request.event_timestamp_utc}'."
            ),
        )

    morning_queue: MorningQueuePayload | None = None

    if request.status == SOSResolutionStatus.LAPSE:
        morning_queue = MorningQueuePayload(
            oars_affirmation_he=HE["LAPSE_OARS_AFFIRMATION"],
            habit_reset_he=HE["LAPSE_HABIT_RESET"],
            header_he=HE["MORNING_QUEUE_HEADER_HE"],
            queued_at_utc=resolved_at,
        )
        db_service.queue_morning_payload(
            db=db,
            user_id=request.user_id,
            header_he=morning_queue.header_he,
            oars_affirmation_he=morning_queue.oars_affirmation_he,
            habit_reset_he=morning_queue.habit_reset_he,
            queued_at_utc=morning_queue.queued_at_utc,
        )
        ack = HE["RESOLVE_LAPSE_ACK_HE"]
    else:
        ack = HE["RESOLVE_SUCCESS_HE"]

    return SOSResolveResponse(
        user_id=request.user_id,
        event_timestamp_utc=request.event_timestamp_utc,
        status=request.status,
        resolved_at_utc=resolved_at,
        acknowledgement_he=ack,
        morning_queue=morning_queue,
    )
