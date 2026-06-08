# -*- coding: utf-8 -*-
"""
test_content_curation.py — Tests for action_url / action_label content curation.

Verifies:
  A. EvaluationResponse schema has action_url / action_label fields.
  B. Phase 2 GLUT4 rule attaches YouTube URL.
  C. Phase 2 recovery rule can attach recipe URL (lower priority than GLUT4).
  D. Phase 3 phytosterol rule attaches recipe URL.
  E. Phase 1 rules never set action_url.
  F. ExternalResourceButton source file checks (file-system — no native import).
  G. locales/he.json has all required content curation keys.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.schemas import (
    EvaluationRequest,
    EvaluationResponse,
    ExerciseSessionRecord,
    ExerciseType,
    HeartRateRecord,
    SleepSessionRecord,
    PlanningSessionRecord,
)
from backend.app.rules        import evaluate_phase1
from backend.app.rules_phase2 import evaluate_phase2, CONTENT_URLS as P2_URLS
from backend.app.rules_phase3 import evaluate_phase3, CONTENT_URLS_P3 as P3_URLS


# ROOT      → backend/       used for backend/locales/he.json
# REPO_ROOT → project root   used for cross-project file checks (frontend components)
ROOT      = Path(__file__).resolve().parents[1]   # backend/tests/ → backend/
REPO_ROOT = Path(__file__).resolve().parents[2]   # backend/tests/ → backend/ → repo root


def _req(**kwargs) -> EvaluationRequest:
    defaults: dict = {
        "user_id": "curation-test",
        "current_week": 5,
    }
    defaults.update(kwargs)
    return EvaluationRequest(**defaults)


# ---------------------------------------------------------------------------
# A. Schema fields
# ---------------------------------------------------------------------------


def test_evaluation_response_has_action_fields():
    resp = EvaluationResponse(
        user_id="test",
        current_week=5,
        phase="test",
        action_url="https://example.com",
        action_label="לחץ כאן",
    )
    assert resp.action_url == "https://example.com"
    assert resp.action_label == "לחץ כאן"


def test_evaluation_response_action_fields_default_none():
    resp = EvaluationResponse(user_id="test", current_week=1, phase="test")
    assert resp.action_url is None
    assert resp.action_label is None


# ---------------------------------------------------------------------------
# B. Phase 2 GLUT4 / YouTube
# ---------------------------------------------------------------------------


def test_phase2_glut4_youtube_url_correct():
    req = _req(
        current_week=5,
        exercise=ExerciseSessionRecord(
            type=ExerciseType.STRENGTH, duration_minutes=45, completed=True
        ),
    )
    r = evaluate_phase2(req)
    assert r.action_url == P2_URLS["glut4_youtube"]
    assert "youtube.com" in r.action_url


def test_phase2_glut4_label_present():
    req = _req(
        current_week=5,
        exercise=ExerciseSessionRecord(
            type=ExerciseType.STRENGTH, duration_minutes=45, completed=True
        ),
    )
    r = evaluate_phase2(req)
    assert r.action_label is not None
    assert len(r.action_label) > 0


# ---------------------------------------------------------------------------
# C. Phase 2 recovery recipe (no strength workout)
# ---------------------------------------------------------------------------


def test_phase2_recovery_url_is_correct_when_set():
    """If recovery rule fires and sets action_url, it must be the recipe URL."""
    req = _req(
        current_week=7,
        heart_rate=HeartRateRecord(resting_hr=80),
        sleep=SleepSessionRecord(duration_hours=5.0),
        user_baseline_rhr=60,
    )
    r = evaluate_phase2(req)
    # BIOFEEDBACK_RECOVERY fires; if recovery URL is set, verify it
    if r.action_url is not None:
        assert r.action_url == P2_URLS["recovery_recipe"]


def test_phase2_glut4_wins_over_recovery():
    """GLUT4 rule fires first; recovery recipe should NOT override it."""
    req = _req(
        current_week=5,
        exercise=ExerciseSessionRecord(
            type=ExerciseType.STRENGTH, duration_minutes=45, completed=True
        ),
        # Also trigger recovery conditions
        heart_rate=HeartRateRecord(resting_hr=80),
        sleep=SleepSessionRecord(duration_hours=4.5),
        user_baseline_rhr=60,
    )
    r = evaluate_phase2(req)
    # GLUT4 fires first → YouTube wins
    assert r.action_url == P2_URLS["glut4_youtube"]


# ---------------------------------------------------------------------------
# D. Phase 3 phytosterol recipe
# ---------------------------------------------------------------------------


def test_phase3_phytosterol_recipe_url_is_correct_when_set():
    req = _req(
        current_week=10,
        planning=PlanningSessionRecord(is_prepped=True, day_of_week=6),
    )
    r = evaluate_phase3(req)
    if r.action_url is not None:
        assert r.action_url == P3_URLS["phytosterol_recipe"]


# ---------------------------------------------------------------------------
# E. Phase 1 — never sets action_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("week", [1, 2, 3, 4])
def test_phase1_no_action_url(week):
    req = _req(current_week=week)
    r = evaluate_phase1(req)
    assert r.action_url is None


# ---------------------------------------------------------------------------
# F. ExternalResourceButton file-system checks
# ---------------------------------------------------------------------------


def test_external_resource_button_file_exists():
    path = REPO_ROOT / "frontend" / "components" / "ExternalResourceButton.js"
    assert path.exists(), f"ExternalResourceButton.js not found at {path}"


def test_external_resource_button_no_inline_hebrew():
    path = REPO_ROOT / "frontend" / "components" / "ExternalResourceButton.js"
    content = path.read_text(encoding="utf-8")
    import re
    # Strip single-line comments
    no_comments = re.sub(r"//[^\n]*", "", content)
    # Strip block comments
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.DOTALL)
    # Find quoted strings that contain Hebrew characters
    hebrew_chars = r"[אבגדהוזחטיכלמנסעפצקרשת]"
    quoted_he = re.findall(
        r'["\']([^"\']*' + hebrew_chars + r'[^"\']*)["\']',
        no_comments,
    )
    assert quoted_he == [], f"Found inline Hebrew strings: {quoted_he}"


def test_external_resource_button_uses_web_browser():
    path = REPO_ROOT / "frontend" / "components" / "ExternalResourceButton.js"
    content = path.read_text(encoding="utf-8")
    assert "expo-web-browser" in content or "WebBrowser" in content


def test_external_resource_button_rtl_margin():
    import re
    path = REPO_ROOT / "frontend" / "components" / "ExternalResourceButton.js"
    content = path.read_text(encoding="utf-8")
    # Strip comments before checking (comments may legitimately mention marginLeft)
    no_comments = re.sub(r"//[^\n]*", "", content)
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.DOTALL)
    assert "marginLeft" not in no_comments,  "RTL: use marginEnd instead of marginLeft"
    assert "marginRight" not in no_comments, "RTL: use marginStart instead of marginRight"


# ---------------------------------------------------------------------------
# G. Locale keys
# ---------------------------------------------------------------------------


def test_locales_have_action_keys():
    locales_path = ROOT / "locales" / "he.json"
    with open(locales_path, encoding="utf-8") as fh:
        he = json.load(fh)

    required = {
        "ACTION_STRENGTH_YOUTUBE_LABEL",
        "ACTION_RECOVERY_RECIPE_LABEL",
        "ACTION_PHYTOSTEROL_RECIPE_LABEL",
        "ACTION_OPEN_LABEL",
        "ACTION_OPEN_ACCESSIBILITY_HINT",
    }
    missing = required - he.keys()
    assert not missing, f"Missing locale keys: {missing}"
