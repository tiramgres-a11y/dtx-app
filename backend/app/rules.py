# -*- coding: utf-8 -*-
"""
Clinical rules engine — Phase 1 (Weeks 1-4: Reset).

Architecture note (per ROADMAP.md):
  This module is owned exclusively by the Orchestrator.
  Workers have zero access to these rules; they only supply sanitized payloads.
  All user-facing strings are in Hebrew (UTF-8). No DB writes here — caller handles persistence.
"""

from __future__ import annotations

from backend.app.schemas import (
    EvaluationRequest,
    EvaluationResponse,
    MenuAdjustment,
)

# ---------------------------------------------------------------------------
# Hebrew message templates (structured dictionary — single source of truth)
# ---------------------------------------------------------------------------

HE: dict[str, str] = {
    # Sleep rule — OARS Reflection (non-judgmental)
    "sleep_oars_reflection": (
        "שמנו לב שהשינה הלילה הייתה קצרה יותר מהרגיל. "
        "זה לגמרי מובן — החיים מורכבים. "
        "אנחנו כאן איתך, ואנחנו מתאימים את תפריט מחר "
        "כדי לתמוך בגוף שלך בדיוק עכשיו: "
        "יותר חלבון צמחי ואגוזים, פחות פחמימות מורכבות. "
        "תן לגוף את מה שהוא צריך."
    ),
    "sleep_menu_rationale": (
        "שינה קצרה מעלה עמידות לאינסולין. "
        "הפחתת פחמימות מורכבות והגברת חלבון צמחי ואגוזים "
        "מפחיתה עומס גליקמי ותומכת בוויסות הורמוני הרעב."
    ),

    # Sedentary rule — Habit Stack push notification
    "sedentary_push": (
        "⏰ זמן תנועה קצר! "
        "עמוד, מתח את הגב, ועשה 10 צעדים קדימה ואחורה — "
        "רק דקה אחת עכשיו שומרת על רמות הסוכר שלך יציבות לאורך היום."
    ),

    # Strength workout — clinical validation
    "strength_validation": (
        "כל הכבוד על האימון! "
        "השרירים שלך עכשיו פתוחים לקלוט גלוקוז ללא צורך באינסולין — "
        "זהו החלון המטבולי היקר ביותר ביום שלך. "
        "אכול ארוחה עשירה בחלבון תוך 45 דקות כדי למקסם את ההשפעה."
    ),

    # Phase label
    "phase_reset": "שלב 1 — איפוס (שבועות 1–4)",

    # Clinical notes per rule
    "note_sleep_rule_fired": "כלל שינה הופעל: משך שינה מתחת ל-6 שעות.",
    "note_sedentary_rule_fired": "כלל ישיבה ממושכת הופעל: זוהו 60 דקות רצופות ללא תנועה בין 08:00–20:00.",
    "note_strength_rule_fired": "כלל אימון כוח הופעל: אימון נרשם בהצלחה.",
    "note_phase1_only": "הכללים הפעילים שייכים לשלב 1 בלבד (שבועות 1–4).",
}

# ---------------------------------------------------------------------------
# Rule constants
# ---------------------------------------------------------------------------

SLEEP_THRESHOLD_HOURS: float = 6.0
SEDENTARY_THRESHOLD_MINUTES: int = 60
PHASE_1_WEEKS: range = range(1, 5)  # weeks 1–4 inclusive


# ---------------------------------------------------------------------------
# Individual rule functions
# ---------------------------------------------------------------------------

def apply_sleep_rule(request: EvaluationRequest, response: EvaluationResponse) -> None:
    """Rule S1: short sleep → menu adjustment + OARS reflection."""
    if request.sleep is None:
        return
    if request.sleep.duration_hours < SLEEP_THRESHOLD_HOURS:
        response.triggered_rules.append("SLEEP_SHORT")
        response.menu_adjustment = MenuAdjustment(
            reduce_complex_carbs=True,
            increase_plant_protein=True,
            increase_nuts=True,
            rationale_he=HE["sleep_menu_rationale"],
        )
        response.oars_reflection_he = HE["sleep_oars_reflection"]
        response.clinical_notes_he.append(HE["note_sleep_rule_fired"])


def apply_sedentary_rule(request: EvaluationRequest, response: EvaluationResponse) -> None:
    """Rule S2: prolonged idleness in active hours → Hebrew Habit Stack notification."""
    if request.steps is None:
        return
    if request.steps.idle_minutes >= SEDENTARY_THRESHOLD_MINUTES:
        response.triggered_rules.append("SEDENTARY_ALERT")
        response.push_notification_he = HE["sedentary_push"]
        response.clinical_notes_he.append(HE["note_sedentary_rule_fired"])


def apply_strength_rule(request: EvaluationRequest, response: EvaluationResponse) -> None:
    """Rule S3: strength workout logged → clinical validation message in Hebrew."""
    if request.strength is None or not request.strength.logged:
        return
    response.triggered_rules.append("STRENGTH_LOGGED")
    response.strength_validation_he = HE["strength_validation"]
    response.clinical_notes_he.append(HE["note_strength_rule_fired"])


# ---------------------------------------------------------------------------
# Orchestrator entry point
# ---------------------------------------------------------------------------

PHASE_1_RULES = [apply_sleep_rule, apply_sedentary_rule, apply_strength_rule]


def evaluate_phase1(request: EvaluationRequest) -> EvaluationResponse:
    """
    Execute all Phase 1 (Weeks 1–4) clinical rules against the incoming daily records.
    Returns a fully populated EvaluationResponse; caller is responsible for DB persistence.
    """
    response = EvaluationResponse(
        user_id=request.user_id,
        current_week=request.current_week,
        phase=HE["phase_reset"],
        clinical_notes_he=[HE["note_phase1_only"]],
    )

    for rule in PHASE_1_RULES:
        rule(request, response)

    return response
