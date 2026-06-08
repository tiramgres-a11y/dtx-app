# -*- coding: utf-8 -*-
"""
Clinical rules engine — Phase 3 (Weeks 10-13: Maintenance & Modularity).

Architecture (per ROADMAP.md):
  Owned exclusively by the Orchestrator. Zero DB writes — caller handles persistence.
  All user-facing strings are in Hebrew (UTF-8), loaded from locales/he.json.

Orthogonality contract:
  Phase 3 rules run AFTER Phase 1 and Phase 2 rules.
  They APPEND to existing output fields; they never overwrite:
    - nutrition_target (P2) is preserved; phytosterol_target is a separate field
    - oars_reflection_he (P2 recovery) is never replaced; oars_open_question_he is new
    - push_notification_he may be overwritten only when Phase 3 is the more urgent signal

Phase 3 rules:
  P3-1  Predictive Planning  — current_week >= 10 AND planning.is_prepped == False
                               AND day_of_week in {6, 7} (Sat/Sun)
                               → OARS open obstacle question in Hebrew
                               → weekend-prep push notification

  P3-2  Phytosterol Target   — current_week >= 10 AND planning.is_prepped == True
                               → PhytosterolTarget(phytosterols_g=2.0) appended
                               → clinical note in Hebrew
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.schemas import (
    EvaluationRequest,
    EvaluationResponse,
    PhytosterolTarget,
)

# ---------------------------------------------------------------------------
# Locale loader (cached at import time)
# ---------------------------------------------------------------------------

_LOCALES_PATH = Path(__file__).resolve().parents[2] / "locales" / "he.json"


def _load_locales() -> dict[str, str]:
    with open(_LOCALES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


HE3: dict[str, str] = _load_locales()


def _t(key: str) -> str:
    return HE3.get(key, f"[MISSING:{key}]")


# ---------------------------------------------------------------------------
# Rule constants — Phase 3
# ---------------------------------------------------------------------------

PHASE_3_WEEKS: range = range(10, 14)    # weeks 10-13 inclusive

# Content Curation — Phase 3 external resource URLs
CONTENT_URLS_P3: dict[str, str] = {
    # Phytosterol-rich meal recipe (Israeli health food site)
    "phytosterol_recipe": "https://www.hamama.co.il/recipe/sterol-avocado-legumes",
}
WEEKEND_DAYS:  frozenset[int] = frozenset({6, 7})   # ISO: 6=Sat, 7=Sun
PHYTOSTEROL_TARGET_G: float = 2.0       # grams/day — ESC guideline

# ---------------------------------------------------------------------------
# Rule P3-1 — Predictive Planning
# ---------------------------------------------------------------------------

def apply_predictive_planning_rule(
    request: EvaluationRequest, response: EvaluationResponse
) -> None:
    """
    P3-1: weekend AND is_prepped == False
    → OARS open obstacle question + push notification.

    Orthogonality: writes to oars_open_question_he (new Phase 3 field),
    never touches oars_reflection_he or oars_affirmation_he.
    push_notification_he is updated only when not already set by a higher-priority rule;
    if Phase 2 already wrote a recovery push, planning push is appended to clinical_notes
    to avoid silent loss of the recovery signal.
    """
    if request.planning is None:
        return

    if request.planning.is_prepped:
        return  # prepped → phytosterol rule handles this case

    if request.planning.day_of_week not in WEEKEND_DAYS:
        return  # planning obstacle question only fires on weekends

    response.triggered_rules.append("PLANNING_OBSTACLE")
    response.oars_open_question_he = _t("P3_PLANNING_OARS_QUESTION")
    response.clinical_notes_he.append(_t("P3_PLANNING_NOTE"))

    # Push: set if nothing higher-priority already occupies the slot
    if response.push_notification_he is None:
        response.push_notification_he = _t("P3_PLANNING_PUSH")
    else:
        # Log the planning push as a clinical note instead of overwriting
        response.clinical_notes_he.append(
            f"תזכורת תכנון (לא נשלחה — עדיפות נמוכה יותר): {_t('P3_PLANNING_PUSH')}"
        )


# ---------------------------------------------------------------------------
# Rule P3-2 — Phytosterol Target
# ---------------------------------------------------------------------------

def apply_phytosterol_rule(
    request: EvaluationRequest, response: EvaluationResponse
) -> None:
    """
    P3-2: is_prepped == True
    → PhytosterolTarget appended as a separate field.

    Orthogonality: phytosterol_target is a new field introduced in Phase 3.
    It coexists with nutrition_target (Phase 2 protein/MUFA targets) — both
    fields are present and non-null when both P2 and P3 rules fire simultaneously.
    """
    if request.planning is None:
        return

    if not request.planning.is_prepped:
        return

    response.triggered_rules.append("PHYTOSTEROL_TARGET")
    response.phytosterol_target = PhytosterolTarget(
        phytosterols_g=PHYTOSTEROL_TARGET_G,
        source_example=_t("P3_PHYTOSTEROL_SOURCE"),
        rationale_he=_t("P3_PHYTOSTEROL_RATIONALE"),
    )
    response.clinical_notes_he.append(_t("P3_PHYTOSTEROL_NOTE"))
    # Content Curation: attach phytosterol recipe only when no prior URL set
    if response.action_url is None:
        response.action_url   = CONTENT_URLS_P3["phytosterol_recipe"]
        response.action_label = _t("ACTION_PHYTOSTEROL_RECIPE_LABEL")


# ---------------------------------------------------------------------------
# Phase 3 Orchestrator entry point
# ---------------------------------------------------------------------------

PHASE_3_RULES = [apply_predictive_planning_rule, apply_phytosterol_rule]


def evaluate_phase3(request: EvaluationRequest) -> EvaluationResponse:
    """
    Execute Phase 1 + Phase 2 + Phase 3 rules for weeks 10-13.

    Execution order guarantees orthogonality:
      1. Phase 1 rules  (sleep, sedentary, legacy strength)
      2. Phase 2 rules  (GLUT4, bio-feedback / recovery)
      3. Phase 3 rules  (predictive planning, phytosterol target)

    Each phase only appends; later phases never zero-out earlier phases' output.
    """
    from backend.app.rules        import apply_sleep_rule, apply_sedentary_rule, apply_strength_rule
    from backend.app.rules_phase2 import apply_glut4_rule, apply_recovery_biofeedback_rule

    response = EvaluationResponse(
        user_id=request.user_id,
        current_week=request.current_week,
        phase=_t("P3_PHASE_LABEL"),
        clinical_notes_he=[_t("P3_NOTE")],
    )

    # ── Phase 1 cascade ─────────────────────────────────────────────────────
    for rule in [apply_sleep_rule, apply_sedentary_rule, apply_strength_rule]:
        rule(request, response)

    # ── Phase 2 cascade ─────────────────────────────────────────────────────
    for rule in [apply_glut4_rule, apply_recovery_biofeedback_rule]:
        rule(request, response)

    # ── Phase 3 rules ────────────────────────────────────────────────────────
    for rule in PHASE_3_RULES:
        rule(request, response)

    return response
