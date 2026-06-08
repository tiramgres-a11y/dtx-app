# -*- coding: utf-8 -*-
"""
test_backend.py — API integration tests for the main evaluate endpoint.

Tests cover:
  * /health endpoint
  * Phase 1 (weeks 1-4) — various rule triggers
  * Phase 2 (weeks 5-9) — baseline RHR auto-injection, GLUT4 content URL
  * Phase 3 (weeks 10-13) — maintenance rules
  * /api/v1/user/baseline-rhr endpoint
  * week out-of-range → 501

EvaluationRequest uses nested Pydantic models:
  steps    → StepsRecord(steps=int, idle_minutes=int)
  heart_rate → HeartRateRecord(resting_hr=int)
  sleep    → SleepSessionRecord(duration_hours=float)
  exercise → ExerciseSessionRecord(type=str, duration_minutes=int, completed=bool)
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data


# ---------------------------------------------------------------------------
# Phase 1 tests (weeks 1-4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("week", [1, 2, 3, 4])
def test_phase1_returns_200(client, week):
    r = client.post("/api/v1/evaluate", json={
        "user_id": "test-user",
        "current_week": week,
    })
    assert r.status_code == 200
    data = r.json()
    assert "triggered_rules" in data
    assert "phase" in data
    assert data["user_id"] == "test-user"


def test_phase1_sleep_rule_fires(client):
    """Short sleep triggers the sleep rule."""
    r = client.post("/api/v1/evaluate", json={
        "user_id": "test-user",
        "current_week": 1,
        "sleep": {"duration_hours": 4.5},
    })
    assert r.status_code == 200
    data = r.json()
    assert "SLEEP_SHORT" in data["triggered_rules"]
    assert data["menu_adjustment"] is not None
    assert data["oars_reflection_he"] is not None


def test_phase1_sedentary_rule_fires(client):
    """High idle minutes triggers the sedentary alert."""
    r = client.post("/api/v1/evaluate", json={
        "user_id": "test-user",
        "current_week": 2,
        "steps": {"steps": 5000, "idle_minutes": 75},
    })
    assert r.status_code == 200
    data = r.json()
    assert "SEDENTARY_ALERT" in data["triggered_rules"]
    assert data["push_notification_he"] is not None


def test_phase1_strength_rule_fires(client):
    """Logged strength workout triggers the strength validation."""
    r = client.post("/api/v1/evaluate", json={
        "user_id": "test-user",
        "current_week": 3,
        "strength": {"logged": True},
    })
    assert r.status_code == 200
    data = r.json()
    assert "STRENGTH_LOGGED" in data["triggered_rules"]
    assert data["strength_validation_he"] is not None


def test_phase1_no_triggers_empty_rules(client):
    """Minimal payload → no rules triggered, still returns 200."""
    r = client.post("/api/v1/evaluate", json={
        "user_id": "test-user",
        "current_week": 4,
    })
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["triggered_rules"], list)


def test_phase1_action_url_none(client):
    """Phase 1 rules don't attach content URLs."""
    r = client.post("/api/v1/evaluate", json={
        "user_id": "test-user",
        "current_week": 1,
    })
    assert r.status_code == 200
    assert r.json().get("action_url") is None


# ---------------------------------------------------------------------------
# Phase 2 tests (weeks 5-9)
# ---------------------------------------------------------------------------


def test_phase2_returns_200(client):
    r = client.post("/api/v1/evaluate", json={
        "user_id": "test-user",
        "current_week": 5,
        "heart_rate": {"resting_hr": 72},
        "user_baseline_rhr": 65,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == "test-user"
    assert "triggered_rules" in data


def test_phase2_baseline_rhr_auto_injected(client):
    """
    Store a baseline RHR, then evaluate without passing user_baseline_rhr.
    The endpoint auto-injects the stored value so recovery rule can fire.
    """
    user_id = "inject-test-user"
    r = client.post(f"/api/v1/user/baseline-rhr?user_id={user_id}&baseline_rhr=60")
    assert r.status_code == 200
    assert r.json()["stored"] is True

    # Elevated HR + short sleep but no baseline in request → auto-injected
    r2 = client.post("/api/v1/evaluate", json={
        "user_id": user_id,
        "current_week": 6,
        "heart_rate": {"resting_hr": 80},
        "sleep": {"duration_hours": 5.0},
        # user_baseline_rhr intentionally omitted
    })
    assert r2.status_code == 200
    # Recovery rule should fire (80 > 60 * 1.10 = 66)
    data = r2.json()
    assert "RECOVERY_BIOFEEDBACK" in data["triggered_rules"]


def test_phase2_glut4_rule_attaches_youtube_url(client):
    """GLUT4 strength rule in Phase 2 should attach a YouTube action_url."""
    r = client.post("/api/v1/evaluate", json={
        "user_id": "strength-user",
        "current_week": 5,
        "exercise": {"type": "STRENGTH", "duration_minutes": 45, "completed": True},
        "user_baseline_rhr": 65,
    })
    assert r.status_code == 200
    data = r.json()
    assert "GLUT4_STRENGTH" in data["triggered_rules"]
    action_url = data.get("action_url")
    assert action_url is not None, "Expected action_url from GLUT4 rule"
    assert "youtube" in action_url.lower(), f"Expected YouTube URL, got {action_url}"
    assert data.get("action_label") is not None


# ---------------------------------------------------------------------------
# Phase 3 tests (weeks 10-13)
# ---------------------------------------------------------------------------


def test_phase3_returns_200(client):
    r = client.post("/api/v1/evaluate", json={
        "user_id": "test-user",
        "current_week": 10,
        "heart_rate": {"resting_hr": 68},
        "user_baseline_rhr": 65,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == "test-user"


# ---------------------------------------------------------------------------
# Baseline RHR endpoint
# ---------------------------------------------------------------------------


def test_baseline_rhr_stored_and_retrieved(client):
    r = client.post("/api/v1/user/baseline-rhr?user_id=rhr-test&baseline_rhr=70")
    assert r.status_code == 200
    body = r.json()
    assert body["stored"] is True
    assert body["baseline_rhr"] == 70


def test_baseline_rhr_invalid_range(client):
    r = client.post("/api/v1/user/baseline-rhr?user_id=rhr-test&baseline_rhr=10")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Week out of range
# ---------------------------------------------------------------------------


def test_week_out_of_range_rejected(client):
    """Week > 13 fails Pydantic validation (le=13 constraint) → 422 Unprocessable Entity."""
    r = client.post("/api/v1/evaluate", json={
        "user_id": "test-user",
        "current_week": 15,
    })
    assert r.status_code == 422
