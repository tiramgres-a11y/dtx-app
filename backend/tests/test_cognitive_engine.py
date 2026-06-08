# -*- coding: utf-8 -*-
"""
test_cognitive_engine.py — Unit tests for the clinical rules engines.

Tests evaluate_phase1/2/3 directly (no HTTP overhead).
Uses correct EvaluationRequest schema with nested sub-models.

EvaluationRequest fields:
  sleep    → SleepSessionRecord(duration_hours=float)
  steps    → StepsRecord(steps=int, idle_minutes=int)
  strength → StrengthWorkoutRecord(logged=bool)
  exercise → ExerciseSessionRecord(type=ExerciseType, duration_minutes=int, completed=bool)
  heart_rate → HeartRateRecord(resting_hr=int)
  planning → PlanningSessionRecord(is_prepped=bool, day_of_week=int)
  user_baseline_rhr → Optional[int]
"""

from __future__ import annotations

import pytest

from backend.app.schemas import (
    EvaluationRequest,
    SleepSessionRecord,
    StepsRecord,
    StrengthWorkoutRecord,
    ExerciseSessionRecord,
    ExerciseType,
    HeartRateRecord,
    PlanningSessionRecord,
)
from backend.app.rules        import evaluate_phase1
from backend.app.rules_phase2 import evaluate_phase2
from backend.app.rules_phase3 import evaluate_phase3


def _req(**kwargs) -> EvaluationRequest:
    defaults: dict = {
        "user_id": "unit-test-user",
        "current_week": 1,
    }
    defaults.update(kwargs)
    return EvaluationRequest(**defaults)


# ---------------------------------------------------------------------------
# Phase 1 — weeks 1-4
# ---------------------------------------------------------------------------


def test_phase1_response_has_required_fields():
    req = _req(current_week=1)
    r = evaluate_phase1(req)
    assert r.user_id == "unit-test-user"
    assert r.current_week == 1
    assert r.phase  # non-empty Hebrew phase label
    assert isinstance(r.triggered_rules, list)
    assert isinstance(r.clinical_notes_he, list)


def test_phase1_no_input_no_rules_fired():
    req = _req(current_week=1)
    r = evaluate_phase1(req)
    # With no sleep/steps/strength data, no rules should fire
    assert r.triggered_rules == []


def test_phase1_sleep_short_triggers_rule():
    req = _req(
        current_week=1,
        sleep=SleepSessionRecord(duration_hours=5.0),
    )
    r = evaluate_phase1(req)
    assert "SLEEP_SHORT" in r.triggered_rules
    assert r.menu_adjustment is not None
    assert r.menu_adjustment.reduce_complex_carbs is True
    assert r.oars_reflection_he is not None


def test_phase1_sleep_adequate_no_rule():
    req = _req(
        current_week=2,
        sleep=SleepSessionRecord(duration_hours=7.5),
    )
    r = evaluate_phase1(req)
    assert "SLEEP_SHORT" not in r.triggered_rules
    assert r.menu_adjustment is None


def test_phase1_sedentary_triggers_push():
    req = _req(
        current_week=1,
        steps=StepsRecord(steps=4000, idle_minutes=90),
    )
    r = evaluate_phase1(req)
    assert "SEDENTARY_ALERT" in r.triggered_rules
    assert r.push_notification_he is not None


def test_phase1_sedentary_below_threshold_no_push():
    req = _req(
        current_week=1,
        steps=StepsRecord(steps=8000, idle_minutes=30),
    )
    r = evaluate_phase1(req)
    assert "SEDENTARY_ALERT" not in r.triggered_rules


def test_phase1_strength_logged_fires_validation():
    req = _req(
        current_week=3,
        strength=StrengthWorkoutRecord(logged=True),
    )
    r = evaluate_phase1(req)
    assert "STRENGTH_LOGGED" in r.triggered_rules
    assert r.strength_validation_he is not None


def test_phase1_strength_not_logged_no_validation():
    req = _req(
        current_week=3,
        strength=StrengthWorkoutRecord(logged=False),
    )
    r = evaluate_phase1(req)
    assert "STRENGTH_LOGGED" not in r.triggered_rules


def test_phase1_all_weeks_return_response():
    for week in [1, 2, 3, 4]:
        req = _req(current_week=week)
        r = evaluate_phase1(req)
        assert r.current_week == week
        assert r.phase


def test_phase1_action_url_always_none():
    req = _req(current_week=1, sleep=SleepSessionRecord(duration_hours=4.0))
    r = evaluate_phase1(req)
    assert r.action_url is None


# ---------------------------------------------------------------------------
# Phase 2 — weeks 5-9
# ---------------------------------------------------------------------------


def test_phase2_response_has_required_fields():
    req = _req(current_week=5)
    r = evaluate_phase2(req)
    assert r.user_id == "unit-test-user"
    assert r.phase


def test_phase2_glut4_strength_fires():
    req = _req(
        current_week=5,
        exercise=ExerciseSessionRecord(
            type=ExerciseType.STRENGTH, duration_minutes=45, completed=True
        ),
    )
    r = evaluate_phase2(req)
    assert "GLUT4_STRENGTH" in r.triggered_rules
    assert r.oars_affirmation_he is not None
    assert r.action_url is not None
    assert "youtube" in r.action_url.lower()
    assert r.action_label is not None


def test_phase2_glut4_not_completed_no_fire():
    req = _req(
        current_week=6,
        exercise=ExerciseSessionRecord(
            type=ExerciseType.STRENGTH, duration_minutes=45, completed=False
        ),
    )
    r = evaluate_phase2(req)
    assert "GLUT4_STRENGTH" not in r.triggered_rules


def test_phase2_cardio_fires_cardio_rule():
    req = _req(
        current_week=7,
        exercise=ExerciseSessionRecord(
            type=ExerciseType.CARDIO, duration_minutes=30, completed=True
        ),
    )
    r = evaluate_phase2(req)
    assert "CARDIO_COMPLETED" in r.triggered_rules


def test_phase2_recovery_biofeedback_fires():
    """HR >10% above baseline + sleep <6h → BIOFEEDBACK_RECOVERY."""
    req = _req(
        current_week=6,
        heart_rate=HeartRateRecord(resting_hr=80),
        sleep=SleepSessionRecord(duration_hours=5.0),
        user_baseline_rhr=60,  # 80 > 60 * 1.10 = 66
    )
    r = evaluate_phase2(req)
    assert "RECOVERY_BIOFEEDBACK" in r.triggered_rules
    assert r.nutrition_target is not None
    assert r.nutrition_target.plant_protein_g > 0


def test_phase2_recovery_no_fire_adequate_sleep():
    """Elevated HR but adequate sleep → recovery rule does NOT fire."""
    req = _req(
        current_week=6,
        heart_rate=HeartRateRecord(resting_hr=80),
        sleep=SleepSessionRecord(duration_hours=7.5),
        user_baseline_rhr=60,
    )
    r = evaluate_phase2(req)
    assert "BIOFEEDBACK_RECOVERY" not in r.triggered_rules


def test_phase2_all_weeks_return_response():
    for week in [5, 6, 7, 8, 9]:
        req = _req(current_week=week)
        r = evaluate_phase2(req)
        assert r.current_week == week


# ---------------------------------------------------------------------------
# Phase 3 — weeks 10-13
# ---------------------------------------------------------------------------


def test_phase3_response_has_required_fields():
    req = _req(current_week=10)
    r = evaluate_phase3(req)
    assert r.user_id == "unit-test-user"
    assert r.phase


def test_phase3_all_weeks_return_response():
    for week in [10, 11, 12, 13]:
        req = _req(current_week=week)
        r = evaluate_phase3(req)
        assert r.current_week == week


# ---------------------------------------------------------------------------
# Schema field presence check
# ---------------------------------------------------------------------------


def test_evaluation_response_has_action_fields():
    req = _req(current_week=1)
    r = evaluate_phase1(req)
    assert hasattr(r, "action_url")
    assert hasattr(r, "action_label")
    # Phase 1 → both should be None
    assert r.action_url is None
    assert r.action_label is None
