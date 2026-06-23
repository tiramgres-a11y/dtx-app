# -*- coding: utf-8 -*-
"""
Pydantic schemas for the DTx clinical rules engine.
  Phase 1 — Weeks 1-4:   Reset
  Phase 2 — Weeks 5-9:   Overload (GLUT4, Bio-feedback / Recovery)
  Phase 3 — Weeks 10-13: Maintenance & Modularity (Predictive Planning, Phytosterols)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Inbound health record schemas (from Worker 1 / Health Data Fetcher)
# ---------------------------------------------------------------------------

class SleepSessionRecord(BaseModel):
    duration_hours: float = Field(..., ge=0.0, le=24.0,
                                  description="Total sleep duration in hours")


class StepsRecord(BaseModel):
    steps: int = Field(..., ge=0,
                       description="Total steps recorded for the day")
    idle_minutes: int = Field(..., ge=0,
                               description="Continuous idle minutes in the 08:00–20:00 window")


class StrengthWorkoutRecord(BaseModel):
    """Phase 1 legacy strength record (logged: bool)."""
    logged: bool = Field(default=False,
                         description="True if a strength workout was logged today")
    duration_minutes: Optional[int] = Field(default=None, ge=0)


# ── Phase 2 additions ────────────────────────────────────────────────────────

class ExerciseType(str, Enum):
    STRENGTH = "STRENGTH"
    CARDIO   = "CARDIO"


class ExerciseSessionRecord(BaseModel):
    """
    Phase 2 exercise session — richer than StrengthWorkoutRecord.
    Replaces / coexists with StrengthWorkoutRecord; both accepted in EvaluationRequest.
    """
    type: ExerciseType = Field(..., description="STRENGTH or CARDIO")
    duration_minutes: int = Field(..., ge=0,
                                   description="Session duration in minutes")
    completed: bool = Field(...,
                            description="True if session was completed as planned")


class HeartRateRecord(BaseModel):
    """Resting heart rate reading for the day (from Health Connect or manual entry)."""
    resting_hr: int = Field(..., ge=20, le=250,
                             description="Resting heart rate in BPM")


# ── Phase 3 additions ────────────────────────────────────────────────────────

class PlanningSessionRecord(BaseModel):
    """
    Phase 3 — Weekly meal-prep planning status.
    Tracks whether the user completed meal prep (קופסאות) planning on the weekend.
    day_of_week follows ISO weekday: 1=Monday … 5=Friday, 6=Saturday, 7=Sunday.
    """
    is_prepped: bool = Field(...,
                             description="True if meal prep session was completed")
    day_of_week: int = Field(..., ge=1, le=7,
                              description="ISO weekday (1=Mon … 7=Sun)")


# ---------------------------------------------------------------------------
# Evaluation request — sent by Worker 2 (Frontend) after daily data collection
# ---------------------------------------------------------------------------

class HealthMetricsRequest(BaseModel):
    """
    Wearable metrics pushed from the dashboard after a Health Connect sync,
    persisted server-side so the AI mentor can read them later.
    All metric fields optional — a partial sync only updates what it has.
    """
    user_id: str = Field(..., description="Opaque user identifier")
    metric_date: Optional[str] = Field(
        default=None, description="YYYY-MM-DD; defaults to server UTC date when omitted"
    )
    sleep_hours: Optional[float] = Field(default=None, ge=0.0, le=24.0)
    steps: Optional[int] = Field(default=None, ge=0)
    idle_minutes: Optional[int] = Field(default=None, ge=0)
    resting_hr: Optional[int] = Field(default=None, ge=20, le=250)


class EvaluationRequest(BaseModel):
    user_id: str = Field(..., description="Opaque user identifier")
    current_week: int = Field(..., ge=1, le=13,
                               description="Current week in the 13-week clinical program")
    # Phase 1 fields
    sleep:    Optional[SleepSessionRecord]    = None
    steps:    Optional[StepsRecord]           = None
    strength: Optional[StrengthWorkoutRecord] = None
    # Phase 2 additions
    exercise:            Optional[ExerciseSessionRecord] = None
    heart_rate:          Optional[HeartRateRecord]       = None
    user_baseline_rhr:   Optional[int] = Field(
        default=None, ge=20, le=250,
        description="User's personal baseline resting HR — looked up from mock_state.json"
    )
    # Phase 3 additions
    planning:            Optional[PlanningSessionRecord] = None


# ---------------------------------------------------------------------------
# Menu adjustment — modified by Orchestrator sleep / recovery rules
# ---------------------------------------------------------------------------

class MenuAdjustment(BaseModel):
    reduce_complex_carbs:   bool = False
    increase_plant_protein: bool = False
    increase_nuts:          bool = False
    rationale_he:           str  = ""


# ---------------------------------------------------------------------------
# Phase 2 nutrition target — precise gram targets for recovery protocol
# ---------------------------------------------------------------------------

class NutritionTarget(BaseModel):
    """
    Emitted by the Bio-feedback / Recovery rule when resting HR is elevated
    AND sleep is short.  Contains specific gram targets for the day's meals.
    """
    plant_protein_g:          int  = Field(..., ge=0,
                                            description="Target plant protein in grams")
    mufa_g:                   int  = Field(..., ge=0,
                                            description="Target MUFA (nuts/seeds/olive oil) in grams")
    reduce_workout_intensity: bool = Field(...,
                                            description="True → scale back today's planned workout")
    intensity_label_he:       str  = Field(default="",
                                            description="Hebrew label for reduced intensity recommendation")
    rationale_he:             str  = Field(default="",
                                            description="Clinical rationale in Hebrew")


# ---------------------------------------------------------------------------
# Phase 3 nutritional target — Phytosterol supplementation
# ---------------------------------------------------------------------------

class PhytosterolTarget(BaseModel):
    """
    Emitted by the Phytosterol rule (Phase 3) when meal prep is confirmed.
    Appended orthogonally to any existing NutritionTarget — never overwrites
    plant_protein_g or mufa_g targets set by Phase 2 rules.
    """
    phytosterols_g:  float = Field(..., ge=0.0,
                                   description="Daily phytosterol target in grams (e.g. 2.0)")
    source_example:  str   = Field(default="",
                                   description="Example food sources in Hebrew")
    rationale_he:    str   = Field(default="",
                                   description="Clinical rationale for phytosterol addition in Hebrew")


# ---------------------------------------------------------------------------
# Outbound evaluation response — from Orchestrator to Worker 2
# ---------------------------------------------------------------------------

class EvaluationResponse(BaseModel):
    user_id:      str
    current_week: int
    phase:        str
    triggered_rules:   list[str] = Field(default_factory=list)
    # Phase 1 fields
    menu_adjustment:       Optional[MenuAdjustment] = None
    oars_reflection_he:    Optional[str]            = None
    push_notification_he:  Optional[str]            = None
    strength_validation_he: Optional[str]           = None
    clinical_notes_he:     list[str]                = Field(default_factory=list)
    # Phase 2 additions
    oars_affirmation_he:   Optional[str]             = None
    nutrition_target:      Optional[NutritionTarget] = None
    workout_intensity_he:  Optional[str]             = None
    # Phase 3 additions
    oars_open_question_he: Optional[str]             = None
    phytosterol_target:    Optional[PhytosterolTarget] = None
    # Content Curation — deep-link to contextual external resources
    # Null-safe: both fields must be non-null for the frontend to render the button.
    action_url:   Optional[str] = Field(
        default=None,
        description="External resource URL (YouTube exercise, recipe site, etc.)"
    )
    action_label: Optional[str] = Field(
        default=None,
        description="Hebrew CTA label for the external resource button (from locales/he.json)"
    )
