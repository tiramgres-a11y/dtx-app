# -*- coding: utf-8 -*-
"""
Clinical rules engine — Phase 2 (Weeks 5-9: Overload).

Architecture (per ROADMAP.md):
  Owned exclusively by the Orchestrator. Zero DB writes — caller handles persistence.
  All user-facing strings are in Hebrew (UTF-8).

Phase 2 rules cascade ON TOP of Phase 1 rules when applicable.
Phase 1 rules (sleep, sedentary, legacy strength) still execute for overlapping triggers;
Phase 2 adds:
  P2-1  GLUT4 Strength Affirmation  — ExerciseSessionRecord(STRENGTH, completed=True)
  P2-2  Bio-Feedback / Recovery     — HeartRateRecord.resting_hr > 10% above baseline
                                      AND SleepSessionRecord.duration_hours < 6.0

Both Phase 1 and Phase 2 rule sets run; no rule overwrites another's output fields.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.schemas import (
    EvaluationRequest,
    EvaluationResponse,
    ExerciseType,
    MenuAdjustment,
    NutritionTarget,
)

# ---------------------------------------------------------------------------
# Hebrew message templates — Phase 2
# (Parallel to Phase 1 HE dict; never mutates Phase 1 entries)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Locale loader for action labels (same pattern as rules_phase3.py)
# ---------------------------------------------------------------------------

_LOCALES_PATH_P2 = Path(__file__).resolve().parents[2] / "locales" / "he.json"

def _load_locales_p2() -> dict[str, str]:
    with open(_LOCALES_PATH_P2, encoding="utf-8") as fh:
        return json.load(fh)

_HE_LOCALES_P2: dict[str, str] = _load_locales_p2()

def _t2(key: str) -> str:
    return _HE_LOCALES_P2.get(key, f"[MISSING:{key}]")

# ---------------------------------------------------------------------------
# Content Curation — mock URLs attached to Phase 2 rule outputs
# These point to curated external resources that open in the in-app browser.
# ---------------------------------------------------------------------------

CONTENT_URLS: dict[str, str] = {
    # P2-1 GLUT4: compound strength training for diabetes prevention (YouTube)
    "glut4_youtube": "https://www.youtube.com/watch?v=Gl2ND2KqDIs",
    # P2-2 Recovery: anti-inflammatory plant-protein meal (recipe site)
    "recovery_recipe": "https://www.hamama.co.il/recipe/salad-quinoa-tofu",
}

HE2: dict[str, str] = {
    # Phase label
    "phase_overload": "שלב 2 — עומס (שבועות 5–9)",

    # Rule P2-1 — GLUT4 Strength Affirmation
    "glut4_affirmation": (
        "כל הכבוד על האימון! "
        "השרירים שלך עכשיו פתוחים וקולטים סוכר ישירות מהדם — ללא צורך באינסולין. "
        "זהו מסלול ה-GLUT4: כאשר שריר מתכווץ, הוא מעביר את קולטני הגלוקוז לפני השטח "
        "ומוריד את הסוכר בדם ללא תלות בהורמון. "
        "אכול ארוחה עם לפחות 30 גרם חלבון תוך 45 דקות כדי לנצל את החלון הזה במלואו."
    ),
    "glut4_note": (
        "כלל GLUT4 הופעל: אימון כוח הושלם — חלון מטבולי פעיל."
    ),

    # Rule P2-1b — Cardio validation
    "cardio_validation": (
        "אימון אירובי מעולה! "
        "קצב לב מוגבר במשך 20+ דקות מגביר את ספיגת הגלוקוז בשרירים "
        "ומשפר את הרגישות לאינסולין ל-24–48 שעות הבאות."
    ),
    "cardio_note": "כלל אירובי הופעל: אימון קרדיו הושלם.",

    # Rule P2-2 — Bio-Feedback / Recovery
    "recovery_oars": (
        "הגוף שלך שולח לנו אות חשוב: "
        "דופק מנוחה גבוה משמעותית מהרגיל, ביחד עם שינה קצרה, "
        "מצביעים על כך שהגוף טרם התאושש. "
        "זה לא חולשה — זה מידע. "
        "אנחנו מתאימים את היום שלך כדי לתמוך בהתאוששות."
    ),
    "recovery_intensity_he": (
        "אימון קל בלבד היום — 30–40% מהעצימות הרגילה. "
        "עדיף הליכה של 20 דקות על פני אימון כוח מלא."
    ),
    "recovery_nutrition_rationale": (
        "דופק מנוחה מוגבר + שינה קצרה = מצב דלקתי נמוך. "
        "50 גרם חלבון צמחי ו-45 גרם MUFA (אגוזים, שמן זית, אבוקדו) "
        "מספקים אנטי-דלקתיים ותומכים בסינתזת חלבון שרירי ללא עומס חיזוי."
    ),
    "recovery_push": (
        "💤 הגוף שלך מבקש מנוחה. "
        "היום: 50 גרם חלבון צמחי, 45 גרם MUFA, ואימון קל בלבד."
    ),
    "recovery_note":  "כלל ביו-פידבק הופעל: דופק מנוחה מוגבר >10% מהבסיס + שינה < 6 שעות.",
    "hr_elevated_note": "דופק מנוחה מוגבר מעל 10% מהבסיס האישי.",
    "sleep_short_note_p2": "שינה קצרה מתחת ל-6 שעות — כלל שלב 2 הופעל.",

    # Phase notes
    "note_phase2": "הכללים הפעילים שייכים לשלב 2 (שבועות 5–9).",
}

# ---------------------------------------------------------------------------
# Rule constants — Phase 2
# ---------------------------------------------------------------------------

PHASE_2_WEEKS: range = range(5, 10)        # weeks 5–9 inclusive
SLEEP_THRESHOLD_HOURS: float = 6.0          # shared with Phase 1 logic
RHR_ELEVATION_RATIO: float = 0.10           # 10% above baseline triggers recovery rule
DEFAULT_BASELINE_RHR: int = 65              # used when no personal baseline is stored
RECOVERY_PLANT_PROTEIN_G: int = 50
RECOVERY_MUFA_G: int = 45

# ---------------------------------------------------------------------------
# Rule P2-1 — GLUT4 Exercise Affirmation
# ---------------------------------------------------------------------------

def apply_glut4_rule(request: EvaluationRequest, response: EvaluationResponse) -> None:
    """
    Rule P2-1: ExerciseSessionRecord with STRENGTH + completed=True
    → OARS affirmation explaining the GLUT4 transporter pathway.

    Does NOT overwrite Phase 1 strength_validation_he; writes to the new
    oars_affirmation_he field so both can coexist in the same response.
    """
    if request.exercise is None:
        return
    if not request.exercise.completed:
        return

    if request.exercise.type == ExerciseType.STRENGTH:
        response.triggered_rules.append("GLUT4_STRENGTH")
        response.oars_affirmation_he = HE2["glut4_affirmation"]
        response.clinical_notes_he.append(HE2["glut4_note"])
        # Content Curation: attach YouTube strength-training resource
        response.action_url   = CONTENT_URLS["glut4_youtube"]
        response.action_label = _t2("ACTION_STRENGTH_YOUTUBE_LABEL")

    elif request.exercise.type == ExerciseType.CARDIO:
        response.triggered_rules.append("CARDIO_COMPLETED")
        # Cardio validation goes to strength_validation_he to avoid adding a new field
        # (oars_affirmation_he reserved for strength GLUT4 message)
        if response.strength_validation_he is None:
            response.strength_validation_he = HE2["cardio_validation"]
        response.clinical_notes_he.append(HE2["cardio_note"])


# ---------------------------------------------------------------------------
# Rule P2-2 — Bio-Feedback / Recovery Rule
# ---------------------------------------------------------------------------

def apply_recovery_biofeedback_rule(
    request: EvaluationRequest, response: EvaluationResponse
) -> None:
    """
    Rule P2-2: resting_hr > (baseline_rhr * 1.10)  AND  sleep < 6.0 hours
    → mutate nutrition payload (50g plant protein, 45g MUFA)
    → reduce scheduled workout intensity
    → OARS recovery reflection

    Uses user_baseline_rhr from request (looked up from mock_state.json by caller).
    Falls back to DEFAULT_BASELINE_RHR when not provided.

    Cascade behaviour:
      - If Phase 1 sleep rule already fired (menu_adjustment present), this rule
        UPGRADES the adjustment with precise gram targets rather than replacing it.
      - oars_reflection_he is overwritten only if recovery context is more urgent
        (HR elevation is a stronger signal than short sleep alone).
    """
    if request.heart_rate is None or request.sleep is None:
        return

    baseline = request.user_baseline_rhr if request.user_baseline_rhr is not None \
               else DEFAULT_BASELINE_RHR

    hr_elevated = request.heart_rate.resting_hr > baseline * (1 + RHR_ELEVATION_RATIO)
    sleep_short = request.sleep.duration_hours < SLEEP_THRESHOLD_HOURS

    if not (hr_elevated and sleep_short):
        return

    # ── Both conditions met — fire recovery protocol ─────────────────────
    response.triggered_rules.append("RECOVERY_BIOFEEDBACK")
    # Content Curation: attach anti-inflammatory recipe (only if GLUT4 didn't
    # already attach a higher-priority strength video URL)
    if response.action_url is None:
        response.action_url   = CONTENT_URLS["recovery_recipe"]
        response.action_label = _t2("ACTION_RECOVERY_RECIPE_LABEL")

    # Clinical notes
    response.clinical_notes_he.append(HE2["hr_elevated_note"])
    response.clinical_notes_he.append(HE2["sleep_short_note_p2"])
    response.clinical_notes_he.append(HE2["recovery_note"])

    # OARS reflection — overwrites Phase 1 sleep reflection (recovery is more specific)
    response.oars_reflection_he = HE2["recovery_oars"]

    # Precise nutrition target (new Phase 2 field)
    response.nutrition_target = NutritionTarget(
        plant_protein_g=RECOVERY_PLANT_PROTEIN_G,
        mufa_g=RECOVERY_MUFA_G,
        reduce_workout_intensity=True,
        intensity_label_he=HE2["recovery_intensity_he"],
        rationale_he=HE2["recovery_nutrition_rationale"],
    )

    # Workout intensity advisory
    response.workout_intensity_he = HE2["recovery_intensity_he"]

    # Push notification
    response.push_notification_he = HE2["recovery_push"]

    # Upgrade / merge menu_adjustment (does not clobber Phase 1 flags)
    if response.menu_adjustment is None:
        response.menu_adjustment = MenuAdjustment(
            reduce_complex_carbs=True,
            increase_plant_protein=True,
            increase_nuts=True,
            rationale_he=HE2["recovery_nutrition_rationale"],
        )
    else:
        # Phase 1 already set flags; upgrade rationale to Phase 2 precision
        response.menu_adjustment.increase_plant_protein = True
        response.menu_adjustment.increase_nuts = True
        response.menu_adjustment.rationale_he = HE2["recovery_nutrition_rationale"]


# ---------------------------------------------------------------------------
# Phase 2 Orchestrator entry point
# ---------------------------------------------------------------------------

PHASE_2_RULES = [apply_glut4_rule, apply_recovery_biofeedback_rule]


def evaluate_phase2(request: EvaluationRequest) -> EvaluationResponse:
    """
    Execute all Phase 2 (Weeks 5–9) clinical rules.

    Phase 1 rules are intentionally NOT re-run here to avoid double-firing;
    the /evaluate endpoint for weeks 5–9 calls this function exclusively.
    Phase 1 legacy fields (sleep/steps/strength) are still accepted in the
    EvaluationRequest to allow hybrid payloads during transition.
    """
    # Import Phase 1 rules here to allow selective re-use without circular import
    from backend.app.rules import (
        apply_sleep_rule,
        apply_sedentary_rule,
        apply_strength_rule,
    )

    response = EvaluationResponse(
        user_id=request.user_id,
        current_week=request.current_week,
        phase=HE2["phase_overload"],
        clinical_notes_he=[HE2["note_phase2"]],
    )

    # Phase 1 rules run first (sleep, sedentary, legacy strength)
    for rule in [apply_sleep_rule, apply_sedentary_rule, apply_strength_rule]:
        rule(request, response)

    # Phase 2 rules run second — may upgrade / overwrite specific fields
    for rule in PHASE_2_RULES:
        rule(request, response)

    return response
