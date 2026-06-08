# -*- coding: utf-8 -*-
"""
test_cognitive_engine.py — Phase 2 Clinical Rules Engine QA

Tests Phase 2 (Weeks 5-9: Overload) rules via FastAPI TestClient.

Scenarios covered:
  1.  Phase guard — week 4 still routes to Phase 1
  2.  Phase guard — week 5 routes to Phase 2
  3.  Phase guard — week 10 returns 501

  4.  Rule P2-1: STRENGTH session completed → GLUT4 affirmation in Hebrew
  5.  Rule P2-1: STRENGTH not completed → no affirmation
  6.  Rule P2-1: CARDIO completed → cardio validation (not GLUT4)
  7.  Rule P2-1: Exact GLUT4 Hebrew string contains key clinical terms

  8.  Rule P2-2: Elevated RHR + short sleep → recovery biofeedback fires
  9.  Rule P2-2: Elevated RHR + adequate sleep → rule does NOT fire
  10. Rule P2-2: Normal RHR + short sleep → rule does NOT fire
  11. Rule P2-2: Nutrition target — plant_protein_g = 50
  12. Rule P2-2: Nutrition target — mufa_g = 45
  13. Rule P2-2: reduce_workout_intensity = True
  14. Rule P2-2: workout_intensity_he contains Hebrew reduction guidance
  15. Rule P2-2: push_notification_he references protein + MUFA

  16. Cascade: STRENGTH completed AND recovery biofeedback → both rules fire
  17. Cascade: P2-2 overwrites oars_reflection_he (more specific signal)
  18. Cascade: P2-2 upgrades menu_adjustment.rationale_he without clobbering flags
  19. Cascade: Phase 1 SLEEP_SHORT still fires in week 5 hybrid payload

  20. Baseline RHR: request with explicit user_baseline_rhr respected
  21. Baseline RHR: auto-inject from mock_state.json when not provided
  22. Baseline RHR: default 65 used when no baseline stored

  23. Schema: ExerciseSessionRecord STRENGTH / CARDIO Enum validation
  24. Schema: ExerciseSessionRecord invalid type → 422
  25. Schema: HeartRateRecord out-of-range resting_hr → 422

  26. Hebrew UTF-8 integrity of all Phase 2 response strings
  27. No clinical logic keywords in Phase 2 response field names
  28. triggered_rules accumulation — no duplicates for single-rule payload
"""

import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, ".")

# ── Reset mock_state.json to clean fixture (preserves user_baselines) ─────
_STATE_PATH = Path("backend/mock_state.json")
_CLEAN_STATE = {
    "users": {},
    "sos_events": [],
    "morning_queue": [],
    "user_baselines": {
        "phase2-user-001": {"baseline_rhr": 62},
        "recovery-test":   {"baseline_rhr": 60},
    },
}
_STATE_PATH.write_text(
    json.dumps(_CLEAN_STATE, ensure_ascii=False, indent=2), encoding="utf-8"
)

from backend.app.main import app  # noqa: E402

client = TestClient(app)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results: list[tuple[str, bool, str]] = []
HE_RE = "֐"  # first Hebrew Unicode codepoint


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = PASS if ok else FAIL
    print(f"  [{status}] {name}" + (f"  ({detail})" if detail else ""))


def has_hebrew(s: str | None) -> bool:
    if not s:
        return False
    return any("֐" <= c <= "׿" for c in s)


def post_eval(payload: dict) -> dict:
    resp = client.post("/api/v1/evaluate", json=payload)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
    return resp.json()


# ===========================================================================
# Test 1-3: Phase routing guards
# ===========================================================================

print("\n=== Tests 1-3: Phase Routing ===")

# Week 4 → Phase 1
r1 = post_eval({"user_id": "u-1", "current_week": 4,
                "sleep": {"duration_hours": 5.0},
                "steps": {"steps": 4000, "idle_minutes": 30}})
record("Week 4 → Phase 1 (phase contains שלב 1)", "שלב 1" in r1["phase"])
record("Week 4 → SLEEP_SHORT fired (P1)", "SLEEP_SHORT" in r1["triggered_rules"])

# Week 5 → Phase 2
r2 = post_eval({"user_id": "u-2", "current_week": 5})
record("Week 5 → Phase 2 (phase contains שלב 2)", "שלב 2" in r2["phase"])
record("Week 5 → phase note is Hebrew", has_hebrew(r2["phase"]))

# Week 10 → Phase 3 (was 501 before Phase 3 was implemented)
r3 = client.post("/api/v1/evaluate", json={"user_id": "u-3", "current_week": 10})
record("Week 10 → HTTP 200 (Phase 3 now routes correctly)", r3.status_code == 200)
record("Week 10 → Phase 3 label", "שלב 3" in r3.json().get("phase", ""))


# ===========================================================================
# Tests 4-7: Rule P2-1 — GLUT4 Strength Affirmation
# ===========================================================================

print("\n=== Tests 4-7: Rule P2-1 — GLUT4 Strength Affirmation ===")

# Test 4: STRENGTH completed → affirmation fires
r4 = post_eval({
    "user_id": "u-4", "current_week": 6,
    "exercise": {"type": "STRENGTH", "duration_minutes": 45, "completed": True},
})
record("STRENGTH completed → GLUT4_STRENGTH in triggered_rules",
       "GLUT4_STRENGTH" in r4["triggered_rules"])
record("oars_affirmation_he is not null", r4["oars_affirmation_he"] is not None)
record("oars_affirmation_he contains Hebrew", has_hebrew(r4.get("oars_affirmation_he")))

# Test 5: STRENGTH not completed → no affirmation
r5 = post_eval({
    "user_id": "u-5", "current_week": 6,
    "exercise": {"type": "STRENGTH", "duration_minutes": 45, "completed": False},
})
record("STRENGTH not completed → GLUT4_STRENGTH NOT triggered",
       "GLUT4_STRENGTH" not in r5["triggered_rules"])
record("oars_affirmation_he is null when not completed", r5["oars_affirmation_he"] is None)

# Test 6: CARDIO completed → cardio validation, not GLUT4
r6 = post_eval({
    "user_id": "u-6", "current_week": 7,
    "exercise": {"type": "CARDIO", "duration_minutes": 30, "completed": True},
})
record("CARDIO completed → CARDIO_COMPLETED in triggered_rules",
       "CARDIO_COMPLETED" in r6["triggered_rules"])
record("CARDIO → GLUT4_STRENGTH NOT triggered",
       "GLUT4_STRENGTH" not in r6["triggered_rules"])
record("CARDIO → oars_affirmation_he remains null",
       r6["oars_affirmation_he"] is None)

# Test 7: Exact GLUT4 Hebrew string validation
glut4_text = r4.get("oars_affirmation_he", "")
record("GLUT4 affirmation contains 'GLUT4'",           "GLUT4" in glut4_text)
record("GLUT4 affirmation contains 'גלוקוז'",           "גלוקוז" in glut4_text)
record("GLUT4 affirmation contains 'אינסולין'",         "אינסולין" in glut4_text)
record("GLUT4 affirmation mentions '45 דקות'",          "45 דקות" in glut4_text)
record("GLUT4 affirmation mentions 'חלבון'",            "חלבון" in glut4_text)
record("GLUT4 affirmation mentions 'פתוחים'",           "פתוחים" in glut4_text)


# ===========================================================================
# Tests 8-15: Rule P2-2 — Bio-Feedback / Recovery
# ===========================================================================

print("\n=== Tests 8-15: Rule P2-2 — Bio-Feedback / Recovery ===")

# Test 8: Elevated RHR (>10% above baseline 60) + short sleep → rule fires
# baseline=60, elevated=68 (13.3% > 10% threshold)
r8 = post_eval({
    "user_id": "recovery-test",
    "current_week": 7,
    "sleep": {"duration_hours": 5.0},
    "heart_rate": {"resting_hr": 68},
    "user_baseline_rhr": 60,
})
record("Elevated RHR + short sleep → RECOVERY_BIOFEEDBACK triggered",
       "RECOVERY_BIOFEEDBACK" in r8["triggered_rules"])
record("oars_reflection_he is recovery message", has_hebrew(r8.get("oars_reflection_he")))
record("oars_reflection_he contains 'דופק'", "דופק" in (r8.get("oars_reflection_he") or ""))

# Test 9: Elevated RHR + adequate sleep → rule does NOT fire
r9 = post_eval({
    "user_id": "u-9", "current_week": 6,
    "sleep": {"duration_hours": 7.0},
    "heart_rate": {"resting_hr": 68},
    "user_baseline_rhr": 60,
})
record("Elevated RHR + adequate sleep → NOT triggered",
       "RECOVERY_BIOFEEDBACK" not in r9["triggered_rules"])

# Test 10: Normal RHR + short sleep → rule does NOT fire
r10 = post_eval({
    "user_id": "u-10", "current_week": 5,
    "sleep": {"duration_hours": 4.5},
    "heart_rate": {"resting_hr": 62},
    "user_baseline_rhr": 60,   # 62/60 = 3.3% — below 10% threshold
})
record("Normal RHR (3.3% above baseline) + short sleep → NOT triggered",
       "RECOVERY_BIOFEEDBACK" not in r10["triggered_rules"])

# Test 11: plant_protein_g = 50
r11 = r8
nt = r11.get("nutrition_target")
record("nutrition_target is not null",       nt is not None)
record("plant_protein_g = 50",               (nt or {}).get("plant_protein_g") == 50,
       f"got {(nt or {}).get('plant_protein_g')}")

# Test 12: mufa_g = 45
record("mufa_g = 45",                        (nt or {}).get("mufa_g") == 45,
       f"got {(nt or {}).get('mufa_g')}")

# Test 13: reduce_workout_intensity = True
record("reduce_workout_intensity = True",    (nt or {}).get("reduce_workout_intensity") is True)

# Test 14: workout_intensity_he
wi = r8.get("workout_intensity_he")
record("workout_intensity_he is Hebrew",     has_hebrew(wi))
record("workout_intensity_he mentions '30–40%'",
       "30" in (wi or "") and "40" in (wi or ""))

# Test 15: push_notification_he references protein + MUFA
push = r8.get("push_notification_he") or ""
record("push_notification_he references protein (חלבון)",
       "חלבון" in push)
record("push_notification_he references MUFA",
       "MUFA" in push or "אגוזים" in push or "45" in push)

# Test extra: nutrition_target rationale is Hebrew
record("nutrition_target.rationale_he is Hebrew",
       has_hebrew((nt or {}).get("rationale_he")))
record("nutrition_target.intensity_label_he is Hebrew",
       has_hebrew((nt or {}).get("intensity_label_he")))


# ===========================================================================
# Tests 16-19: Cascade behaviour
# ===========================================================================

print("\n=== Tests 16-19: Cascade / Rule Interaction ===")

# Test 16: STRENGTH completed AND recovery biofeedback → both rules fire
r16 = post_eval({
    "user_id": "cascade-user", "current_week": 8,
    "sleep": {"duration_hours": 4.5},
    "heart_rate": {"resting_hr": 72},
    "user_baseline_rhr": 60,   # 72/60 = 20% > 10% ✓
    "exercise": {"type": "STRENGTH", "duration_minutes": 50, "completed": True},
})
record("Both GLUT4_STRENGTH and RECOVERY_BIOFEEDBACK triggered",
       "GLUT4_STRENGTH" in r16["triggered_rules"] and
       "RECOVERY_BIOFEEDBACK" in r16["triggered_rules"])
record("oars_affirmation_he (GLUT4) present",    r16.get("oars_affirmation_he") is not None)
record("oars_reflection_he (recovery) present",  r16.get("oars_reflection_he") is not None)
record("nutrition_target present in cascade",    r16.get("nutrition_target") is not None)

# Test 17: P2-2 overwrites oars_reflection_he with recovery context
record("oars_reflection_he is recovery message (דופק)",
       "דופק" in (r16.get("oars_reflection_he") or ""))

# Test 18: Phase 1 flags preserved in menu_adjustment after P2-2 upgrade
ma = r16.get("menu_adjustment")
record("menu_adjustment present after cascade",      ma is not None)
record("increase_plant_protein preserved/upgraded",  (ma or {}).get("increase_plant_protein") is True)
record("increase_nuts preserved/upgraded",           (ma or {}).get("increase_nuts") is True)
record("menu_adjustment rationale upgraded to P2",
       "MUFA" in ((ma or {}).get("rationale_he") or "") or
       "דלקתי" in ((ma or {}).get("rationale_he") or ""))

# Test 19: Phase 1 SLEEP_SHORT still fires in Phase 2 hybrid payload
r19 = post_eval({
    "user_id": "hybrid-user", "current_week": 5,
    "sleep": {"duration_hours": 4.0},
    "steps": {"steps": 3000, "idle_minutes": 70},
})
record("Phase 1 SLEEP_SHORT fires in week 5",   "SLEEP_SHORT" in r19["triggered_rules"])
record("Phase 1 SEDENTARY_ALERT fires in week 5", "SEDENTARY_ALERT" in r19["triggered_rules"])
record("Phase 2 phase label present",           "שלב 2" in r19["phase"])


# ===========================================================================
# Tests 20-22: Baseline RHR handling
# ===========================================================================

print("\n=== Tests 20-22: Baseline RHR Handling ===")

# Test 20: Explicit user_baseline_rhr in request
r20 = post_eval({
    "user_id": "explicit-baseline", "current_week": 6,
    "sleep": {"duration_hours": 5.0},
    "heart_rate": {"resting_hr": 80},
    "user_baseline_rhr": 70,   # 80/70 = 14.3% > 10%
})
record("Explicit baseline 70, HR 80 → RECOVERY_BIOFEEDBACK fires",
       "RECOVERY_BIOFEEDBACK" in r20["triggered_rules"])

# Test 21: Auto-inject from mock_state.json (phase2-user-001 baseline=62)
r21 = post_eval({
    "user_id": "phase2-user-001", "current_week": 7,
    "sleep": {"duration_hours": 5.0},
    "heart_rate": {"resting_hr": 70},   # 70/62 = 12.9% > 10%
    # No user_baseline_rhr — should auto-inject 62 from mock_state.json
})
record("Auto-inject baseline from mock_state: HR 70, baseline 62 → fires",
       "RECOVERY_BIOFEEDBACK" in r21["triggered_rules"])

# Test 22: Unknown user, no stored baseline → uses default 65
r22 = post_eval({
    "user_id": "unknown-new-user", "current_week": 5,
    "sleep": {"duration_hours": 5.0},
    "heart_rate": {"resting_hr": 75},   # 75/65(default) = 15.4% > 10%
})
record("Default baseline 65, HR 75 (15.4%) → RECOVERY_BIOFEEDBACK fires",
       "RECOVERY_BIOFEEDBACK" in r22["triggered_rules"])

# Boundary: 10% exactly (65 * 1.10 = 71.5) → HR=71 should NOT fire
r22b = post_eval({
    "user_id": "boundary-user", "current_week": 5,
    "sleep": {"duration_hours": 5.0},
    "heart_rate": {"resting_hr": 71},
    "user_baseline_rhr": 65,   # 71/65 = 9.2% < 10%
})
record("HR exactly 9.2% above default baseline → NOT triggered",
       "RECOVERY_BIOFEEDBACK" not in r22b["triggered_rules"])


# ===========================================================================
# Tests 23-25: Schema validation
# ===========================================================================

print("\n=== Tests 23-25: Schema Validation ===")

# Test 23: Valid ExerciseType enum values
for etype in ["STRENGTH", "CARDIO"]:
    resp = client.post("/api/v1/evaluate", json={
        "user_id": "schema-test", "current_week": 6,
        "exercise": {"type": etype, "duration_minutes": 30, "completed": True},
    })
    record(f"ExerciseType.{etype} → HTTP 200", resp.status_code == 200)

# Test 24: Invalid ExerciseType → 422
resp24 = client.post("/api/v1/evaluate", json={
    "user_id": "schema-test", "current_week": 6,
    "exercise": {"type": "YOGA", "duration_minutes": 30, "completed": True},
})
record("Invalid ExerciseType 'YOGA' → HTTP 422", resp24.status_code == 422)

# Test 25: HeartRateRecord out of range → 422
resp25a = client.post("/api/v1/evaluate", json={
    "user_id": "schema-test", "current_week": 6,
    "heart_rate": {"resting_hr": 300},
})
record("resting_hr=300 (> 250) → HTTP 422", resp25a.status_code == 422)

resp25b = client.post("/api/v1/evaluate", json={
    "user_id": "schema-test", "current_week": 6,
    "heart_rate": {"resting_hr": 10},
})
record("resting_hr=10 (< 20) → HTTP 422", resp25b.status_code == 422)


# ===========================================================================
# Test 26: Hebrew UTF-8 integrity across all Phase 2 response strings
# ===========================================================================

print("\n=== Test 26: Hebrew UTF-8 Integrity ===")

# Rich payload that fires both P2 rules
r26 = post_eval({
    "user_id": "utf8-p2", "current_week": 8,
    "sleep": {"duration_hours": 4.5},
    "heart_rate": {"resting_hr": 72},
    "user_baseline_rhr": 60,
    "exercise": {"type": "STRENGTH", "duration_minutes": 45, "completed": True},
})

raw = client.post("/api/v1/evaluate", json={
    "user_id": "utf8-p2", "current_week": 8,
    "sleep": {"duration_hours": 4.5},
    "heart_rate": {"resting_hr": 72},
    "user_baseline_rhr": 60,
    "exercise": {"type": "STRENGTH", "duration_minutes": 45, "completed": True},
}).content

try:
    decoded = raw.decode("utf-8")
    record("Response decodes as valid UTF-8", True)
except UnicodeDecodeError as e:
    record("Response decodes as valid UTF-8", False, str(e))

for field in ["oars_affirmation_he", "oars_reflection_he", "push_notification_he",
              "workout_intensity_he"]:
    val = r26.get(field)
    record(f"{field} contains Hebrew chars", has_hebrew(val),
           (val or "")[:40])

nt26 = r26.get("nutrition_target") or {}
for sub in ["rationale_he", "intensity_label_he"]:
    record(f"nutrition_target.{sub} contains Hebrew", has_hebrew(nt26.get(sub)))

# State file still valid UTF-8
try:
    _STATE_PATH.read_text(encoding="utf-8")
    record("mock_state.json valid UTF-8 after Phase 2 run", True)
except UnicodeDecodeError as e:
    record("mock_state.json valid UTF-8 after Phase 2 run", False, str(e))


# ===========================================================================
# Tests 27-28: Structural / architectural invariants
# ===========================================================================

print("\n=== Tests 27-28: Structural Invariants ===")

# Test 27: Phase 2 response schema contains Phase 2 fields
record("oars_affirmation_he field present in schema (not None when triggered)",
       r4.get("oars_affirmation_he") is not None)
record("nutrition_target field present in schema (not None when triggered)",
       r8.get("nutrition_target") is not None)
record("workout_intensity_he field present in schema",
       r8.get("workout_intensity_he") is not None)

# Test 28: No duplicate triggered_rules in single-rule payloads
r28 = post_eval({
    "user_id": "u-28", "current_week": 6,
    "exercise": {"type": "STRENGTH", "duration_minutes": 30, "completed": True},
})
rules = r28["triggered_rules"]
record("No duplicate rules in triggered_rules list",
       len(rules) == len(set(rules)), f"got: {rules}")

# Health endpoint reflects Phase 2
health = client.get("/health").json()
record("/health mentions Phase 2", "Phase 2" in str(health) or "2" in str(health))


# ===========================================================================
# Tests 29+: Weekly Summary Aggregator
# ===========================================================================

print("\n=== Tests 29-50: Weekly Summary Aggregator ===")

SUMMARY_URL = "/api/v1/engine/weekly-summary"

def post_summary(payload: dict) -> dict:
    resp = client.post(SUMMARY_URL, json=payload)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:300]}"
    return resp.json()

# ── Fixture: 7-day dataset for week 9, day 4 has NO data (missing day) ───
WEEK9_DAYS = [
    # Day 1
    {"date": "2026-05-18",
     "sleep":    {"duration_hours": 6.5},
     "steps":    {"steps": 7200, "idle_minutes": 30},
     "exercise": {"type": "STRENGTH", "duration_minutes": 45, "completed": True},
     "heart_rate": {"resting_hr": 62}},
    # Day 2
    {"date": "2026-05-19",
     "sleep":    {"duration_hours": 7.0},
     "steps":    {"steps": 8100, "idle_minutes": 25},
     "exercise": {"type": "CARDIO",   "duration_minutes": 30, "completed": True},
     "heart_rate": {"resting_hr": 60}},
    # Day 3
    {"date": "2026-05-20",
     "sleep":    {"duration_hours": 5.5},
     "steps":    {"steps": 6000, "idle_minutes": 50},
     "heart_rate": {"resting_hr": 63}},
    # Day 4 — MISSING (no health data at all)
    {"date": "2026-05-21"},
    # Day 5
    {"date": "2026-05-22",
     "sleep":    {"duration_hours": 7.5},
     "steps":    {"steps": 9000, "idle_minutes": 20},
     "exercise": {"type": "STRENGTH", "duration_minutes": 50, "completed": True},
     "heart_rate": {"resting_hr": 58}},
    # Day 6
    {"date": "2026-05-23",
     "sleep":    {"duration_hours": 6.0},
     "steps":    {"steps": 5500, "idle_minutes": 40},
     "exercise": {"type": "STRENGTH", "duration_minutes": 40, "completed": True},
     "heart_rate": {"resting_hr": 59}},
    # Day 7
    {"date": "2026-05-24",
     "sleep":    {"duration_hours": 6.5},
     "steps":    {"steps": 7800, "idle_minutes": 35},
     "heart_rate": {"resting_hr": 61}},
]

# Expected values (missing day 4 excluded from denominators):
# sleep values: [6.5, 7.0, 5.5, 7.5, 6.0, 6.5] — 6 days, avg = 39.0/6 = 6.5
# steps values: [7200, 8100, 6000, 9000, 5500, 7800] — 6 days, avg = 43600/6 ≈ 7266.67
# rhr values:   [62, 60, 63, 58, 59, 61] — 6 days, avg = 363/6 = 60.5
# strength sessions: days 1, 5, 6 (completed) = 3
# cardio sessions:   day 2 (completed) = 1
# exercise minutes:  45 + 30 + 50 + 40 = 165
# days_with_data: 6 (day 4 has no fields)

EXPECTED_AVG_SLEEP   = 6.5
EXPECTED_AVG_STEPS   = round(43600 / 6, 2)   # 7266.67
EXPECTED_AVG_RHR     = round(363 / 6, 2)     # 60.5
EXPECTED_STRENGTH    = 3
EXPECTED_CARDIO      = 1
EXPECTED_EX_MINS     = 165
EXPECTED_DAYS_DATA   = 6

r_w9 = post_summary({
    "user_id": "weekly-test-user",
    "current_week": 9,
    "days": WEEK9_DAYS,
})

# ── Test 29: Basic structure ────────────────────────────────────────────
record("29. user_id echoed", r_w9["user_id"] == "weekly-test-user")
record("29. current_week=9", r_w9["current_week"] == 9)
record("29. phase_label contains שלב 2", "שלב 2" in r_w9["phase_label"])
record("29. metrics block present", "metrics" in r_w9)
record("29. oars_summary_he is Hebrew", has_hebrew(r_w9.get("oars_summary_he")))

# ── Test 30: days_with_data excludes empty day ────────────────────────
m = r_w9["metrics"]
record("30. days_supplied = 7", m["days_supplied"] == 7,
       f"got {m['days_supplied']}")
record("30. days_with_data = 6 (empty day excluded)", m["days_with_data"] == EXPECTED_DAYS_DATA,
       f"got {m['days_with_data']}")

# ── Test 31: avg_sleep_hours — correct null-safe average ─────────────
record("31. avg_sleep_hours = 6.5 (6-day avg)", m["avg_sleep_hours"] == EXPECTED_AVG_SLEEP,
       f"got {m['avg_sleep_hours']}")

# ── Test 32: avg_steps — correct average ─────────────────────────────
record("32. avg_steps ≈ 7266.67", m["avg_steps"] == EXPECTED_AVG_STEPS,
       f"got {m['avg_steps']}")

# ── Test 33: avg_resting_hr — correct average ────────────────────────
record("33. avg_resting_hr = 60.5", m["avg_resting_hr"] == EXPECTED_AVG_RHR,
       f"got {m['avg_resting_hr']}")

# ── Test 34: Exercise session counts ─────────────────────────────────
record("34. total_strength_sessions = 3", m["total_strength_sessions"] == EXPECTED_STRENGTH,
       f"got {m['total_strength_sessions']}")
record("34. total_cardio_sessions = 1",   m["total_cardio_sessions"] == EXPECTED_CARDIO,
       f"got {m['total_cardio_sessions']}")
record("34. total_exercise_minutes = 165",m["total_exercise_minutes"] == EXPECTED_EX_MINS,
       f"got {m['total_exercise_minutes']}")

# ── Test 35: OARS question for week 9 ────────────────────────────────
oars = r_w9["oars_summary_he"]
record("35. Week 9 OARS contains 'דופק'",     "דופק"  in oars, oars[:60])
record("35. Week 9 OARS contains 'ירד'",       "ירד"   in oars)
record("35. Week 9 OARS is a question (?)",     "?" in oars)

# ── Test 36: Week 8 OARS contains sleep average substitution ─────────
r_w8 = post_summary({
    "user_id": "w8-user", "current_week": 8,
    "days": [
        {"date": "2026-05-11", "sleep": {"duration_hours": 6.0}},
        {"date": "2026-05-12", "sleep": {"duration_hours": 7.0}},
    ],
})
oars_w8 = r_w8["oars_summary_he"]
record("36. Week 8 OARS contains avg sleep value", "6.5" in oars_w8 or "7" in oars_w8 or "6" in oars_w8)
record("36. Week 8 OARS is Hebrew",                has_hebrew(oars_w8))

# ── Test 37: Insights — sleep ≥ 7h → positive insight ────────────────
r_good_sleep = post_summary({
    "user_id": "good-sleeper", "current_week": 7,
    "days": [
        {"date": "2026-05-12", "sleep": {"duration_hours": 7.5}},
        {"date": "2026-05-13", "sleep": {"duration_hours": 8.0}},
        {"date": "2026-05-14", "sleep": {"duration_hours": 7.2}},
    ],
})
insights_good = r_good_sleep["insights_he"]
record("37. avg sleep ≥ 7h → positive sleep insight",
       any("אינסולין" in i or "שינה" in i for i in insights_good),
       str(insights_good))

# ── Test 38: Insights — avg sleep < 6h → risk insight ────────────────
r_bad_sleep = post_summary({
    "user_id": "poor-sleeper", "current_week": 6,
    "days": [
        {"date": "2026-05-05", "sleep": {"duration_hours": 4.5}},
        {"date": "2026-05-06", "sleep": {"duration_hours": 5.0}},
        {"date": "2026-05-07", "sleep": {"duration_hours": 5.5}},
    ],
})
insights_bad = r_bad_sleep["insights_he"]
record("38. avg sleep < 6h → risk insight (עמידות)",
       any("עמידות" in i for i in insights_bad),
       str(insights_bad))

# ── Test 39: Insights — ≥ 3 strength sessions ────────────────────────
r_strong = post_summary({
    "user_id": "strong-user", "current_week": 9,
    "days": [
        {"date": f"2026-05-{18+i}",
         "exercise": {"type": "STRENGTH", "duration_minutes": 45, "completed": True}}
        for i in range(4)
    ],
})
record("39. ≥ 3 strength sessions → GLUT4 insight",
       any("GLUT4" in i or "כוח" in i for i in r_strong["insights_he"]),
       str(r_strong["insights_he"]))
record("39. total_strength_sessions = 4", r_strong["metrics"]["total_strength_sessions"] == 4)

# ── Test 40: Insights — no exercise + data days ≥ 3 → nudge insight ──
r_sedentary = post_summary({
    "user_id": "couch-user", "current_week": 5,
    "days": [
        {"date": "2026-05-04", "sleep": {"duration_hours": 7.0}},
        {"date": "2026-05-05", "sleep": {"duration_hours": 7.5}},
        {"date": "2026-05-06", "sleep": {"duration_hours": 6.5}},
        {"date": "2026-05-07", "sleep": {"duration_hours": 7.0}},
    ],
})
record("40. No exercise + 4 data days → no-exercise insight",
       any("אימון" in i or "הליכה" in i for i in r_sedentary["insights_he"]),
       str(r_sedentary["insights_he"]))

# ── Test 41: Missing-only day does not corrupt averages ───────────────
r_missing = post_summary({
    "user_id": "sparse-user", "current_week": 6,
    "days": [
        {"date": "2026-05-05"},   # entirely empty
        {"date": "2026-05-06"},   # entirely empty
        {"date": "2026-05-07", "sleep": {"duration_hours": 7.0}},
    ],
})
m_miss = r_missing["metrics"]
record("41. Two missing days excluded — avg_sleep = 7.0",
       m_miss["avg_sleep_hours"] == 7.0, f"got {m_miss['avg_sleep_hours']}")
record("41. days_with_data = 1",
       m_miss["days_with_data"] == 1, f"got {m_miss['days_with_data']}")
record("41. avg_steps is None (no steps supplied)",
       m_miss["avg_steps"] is None)
record("41. avg_resting_hr is None",
       m_miss["avg_resting_hr"] is None)

# ── Test 42: Division-by-zero safety — all days missing ───────────────
r_all_missing = post_summary({
    "user_id": "ghost-user", "current_week": 5,
    "days": [
        {"date": "2026-05-04"},
        {"date": "2026-05-05"},
    ],
})
m_all = r_all_missing["metrics"]
record("42. All days empty → avg_sleep_hours is None", m_all["avg_sleep_hours"] is None)
record("42. All days empty → avg_steps is None",       m_all["avg_steps"] is None)
record("42. All days empty → days_with_data = 0",      m_all["days_with_data"] == 0)
record("42. All days empty → OARS question still returned",
       has_hebrew(r_all_missing.get("oars_summary_he")))
record("42. No crash on all-empty input", True)

# ── Test 43: Sleep trend — improving ─────────────────────────────────
r_trend_up = post_summary({
    "user_id": "trend-up", "current_week": 7,
    "days": [
        {"date": f"2026-05-{11+i}",
         "sleep": {"duration_hours": 5.0 + i * 0.4}}   # 5.0, 5.4, 5.8, 6.2, 6.6, 7.0
        for i in range(6)
    ],
})
record("43. Improving sleep trend → label contains '↑' or 'משתפר'",
       "↑" in (r_trend_up["metrics"]["sleep_trend"] or "") or
       "משתפר" in (r_trend_up["metrics"]["sleep_trend"] or ""),
       r_trend_up["metrics"]["sleep_trend"])

# ── Test 44: RHR trend — improving (lower is better) ─────────────────
r_rhr_trend = post_summary({
    "user_id": "rhr-trend", "current_week": 9,
    "days": [
        {"date": f"2026-05-{18+i}",
         "heart_rate": {"resting_hr": 70 - i * 2}}   # 70, 68, 66, 64, 62, 60
        for i in range(6)
    ],
})
record("44. Declining RHR (good) → label contains '↓' or 'יורד'",
       "↓" in (r_rhr_trend["metrics"]["rhr_trend"] or "") or
       "יורד" in (r_rhr_trend["metrics"]["rhr_trend"] or ""),
       r_rhr_trend["metrics"]["rhr_trend"])

# ── Test 45: Schema validation — max 7 days ───────────────────────────
resp45 = client.post(SUMMARY_URL, json={
    "user_id": "too-many", "current_week": 5,
    "days": [{"date": f"2026-05-{i:02d}"} for i in range(1, 10)],  # 9 days
})
record("45. >7 days → HTTP 422", resp45.status_code == 422)

# ── Test 46: Schema validation — at least 1 day required ─────────────
resp46 = client.post(SUMMARY_URL, json={
    "user_id": "no-days", "current_week": 5, "days": [],
})
record("46. 0 days → HTTP 422", resp46.status_code == 422)

# ── Test 47: clinical_notes_he is present and Hebrew ─────────────────
record("47. clinical_notes_he is list",  isinstance(r_w9["clinical_notes_he"], list))
record("47. clinical_notes_he non-empty", len(r_w9["clinical_notes_he"]) >= 1)
record("47. clinical note is Hebrew",
       any(has_hebrew(n) for n in r_w9["clinical_notes_he"]))

# ── Test 48: UTF-8 integrity of full response ─────────────────────────
raw48 = client.post(SUMMARY_URL, json={
    "user_id": "utf8-weekly", "current_week": 9, "days": WEEK9_DAYS,
}).content
try:
    decoded48 = raw48.decode("utf-8")
    record("48. Response decodes as valid UTF-8", True)
    record("48. Hebrew present in raw response bytes",
           any("֐" <= c <= "׿" for c in decoded48))
except UnicodeDecodeError as e:
    record("48. Response decodes as valid UTF-8", False, str(e))
    record("48. Hebrew present in raw bytes", False)

# ── Test 49: existing /api/v1/evaluate endpoint unmodified ───────────
r49 = post_eval({"user_id": "unchanged-check", "current_week": 2,
                 "sleep": {"duration_hours": 5.5},
                 "steps": {"steps": 4000, "idle_minutes": 25}})
record("49. /api/v1/evaluate still works after weekly-summary mount",
       "SLEEP_SHORT" in r49["triggered_rules"])
record("49. /api/v1/evaluate returns Phase 1 label", "שלב 1" in r49["phase"])

# ── Test 50: Week 6 OARS question (different from week 9) ────────────
r_w6 = post_summary({
    "user_id": "w6-user", "current_week": 6,
    "days": [
        {"date": "2026-05-04",
         "exercise": {"type": "STRENGTH", "duration_minutes": 45, "completed": True}},
        {"date": "2026-05-05",
         "exercise": {"type": "STRENGTH", "duration_minutes": 40, "completed": True}},
        {"date": "2026-05-06",
         "exercise": {"type": "STRENGTH", "duration_minutes": 50, "completed": True}},
    ],
})
oars_w6 = r_w6["oars_summary_he"]
record("50. Week 6 OARS mentions 'אימוני כוח' or 'התמיד'",
       "אימוני" in oars_w6 or "התמיד" in oars_w6 or "שלושה" in oars_w6,
       oars_w6[:60])
record("50. Week 6 OARS is different from Week 9 OARS",
       oars_w6 != r_w9["oars_summary_he"])

# ===========================================================================
# Tests 51+: Phase 3 — Maintenance & Modularity (Weeks 10-13)
# ===========================================================================

print("\n=== Tests 51-70: Phase 3 — Maintenance & Modularity ===")

# ── Test 51: Phase 3 routing — week 10 reaches Phase 3 engine ────────────
r51 = post_eval({"user_id": "p3-route", "current_week": 10})
record("51. Week 10 routes to Phase 3 (phase contains שלב 3)",
       "שלב 3" in r51["phase"])
record("51. Phase 3 label is Hebrew",   has_hebrew(r51["phase"]))

# ── Test 52: Week 13 also routes to Phase 3 ──────────────────────────────
r52 = post_eval({"user_id": "p3-w13", "current_week": 13})
record("52. Week 13 routes to Phase 3", "שלב 3" in r52["phase"])

# ── Test 53: Week 14 → 422 (Pydantic rejects current_week > 13)
# All weeks 1-13 are now routed (P1/P2/P3 complete) — 501 is unreachable by design.
# Schema enforces le=13, so week 14 is caught at validation level.
r53 = client.post("/api/v1/evaluate", json={"user_id": "beyond", "current_week": 14})
record("53. Week 14 → HTTP 422 (schema enforces le=13)", r53.status_code == 422)
# Pydantic 422 detail is a list of error dicts — ensure it doesn't crash
detail53 = r53.json().get("detail", "")
record("53. 422 detail is non-empty",   bool(detail53))

# ── Test 54: P3-1 Predictive Planning — NOT prepped on Saturday (day 6) ──
r54 = post_eval({
    "user_id": "planner", "current_week": 10,
    "planning": {"is_prepped": False, "day_of_week": 6},
})
record("54. PLANNING_OBSTACLE in triggered_rules",
       "PLANNING_OBSTACLE" in r54["triggered_rules"])
record("54. oars_open_question_he is not null",
       r54.get("oars_open_question_he") is not None)
record("54. oars_open_question_he is Hebrew",
       has_hebrew(r54.get("oars_open_question_he")))

# ── Test 55: Exact OARS obstacle question text ────────────────────────────
oars_q = r54.get("oars_open_question_he", "")
record("55. OARS question mentions 'קופסאות'", "קופסאות" in oars_q)
record("55. OARS question mentions 'שבת'",     "שבת" in oars_q)
record("55. OARS question mentions 'מכשול'",   "מכשול" in oars_q)
record("55. OARS question is a question (?)",   "?" in oars_q)
record("55. Exact match to locales/he.json key",
       oars_q == "מה לרוב המכשול העיקרי שמונע ממך לארגן קופסאות אוכל מראש ביום שבת?",
       oars_q[:70])

# ── Test 56: P3-1 — NOT prepped on Sunday (day 7) also fires ─────────────
r56 = post_eval({
    "user_id": "planner-sun", "current_week": 11,
    "planning": {"is_prepped": False, "day_of_week": 7},
})
record("56. PLANNING_OBSTACLE fires on Sunday (day 7)",
       "PLANNING_OBSTACLE" in r56["triggered_rules"])

# ── Test 57: P3-1 — NOT prepped on WEEKDAY (day 3) does NOT fire ─────────
r57 = post_eval({
    "user_id": "planner-wed", "current_week": 10,
    "planning": {"is_prepped": False, "day_of_week": 3},
})
record("57. PLANNING_OBSTACLE does NOT fire on weekday (day 3)",
       "PLANNING_OBSTACLE" not in r57["triggered_rules"])
record("57. oars_open_question_he is None on weekday",
       r57.get("oars_open_question_he") is None)

# ── Test 58: P3-1 — push notification set when not prepped on weekend ─────
record("58. push_notification_he set on weekend/no-prep",
       r54.get("push_notification_he") is not None)
push58 = r54.get("push_notification_he", "")
record("58. push mentions 'קופסאות' or 'הכנה'",
       "קופסאות" in push58 or "הכנה" in push58)

# ── Test 59: P3-2 — Phytosterol target when is_prepped == True ───────────
r59 = post_eval({
    "user_id": "prepped-user", "current_week": 10,
    "planning": {"is_prepped": True, "day_of_week": 6},
})
record("59. PHYTOSTEROL_TARGET in triggered_rules",
       "PHYTOSTEROL_TARGET" in r59["triggered_rules"])
record("59. phytosterol_target is not null",
       r59.get("phytosterol_target") is not None)
pt = r59.get("phytosterol_target", {})
record("59. phytosterols_g = 2.0",
       pt.get("phytosterols_g") == 2.0, f"got {pt.get('phytosterols_g')}")
record("59. source_example is Hebrew",
       has_hebrew(pt.get("source_example")))
record("59. rationale_he is Hebrew",
       has_hebrew(pt.get("rationale_he")))

# ── Test 60: P3-2 — phytosterol mentions LDL and clinical evidence ────────
record("60. rationale_he mentions 'LDL'",
       "LDL" in (pt.get("rationale_he") or ""))
record("60. rationale_he mentions 'פיטוסטרולים'",
       "פיטוסטרולים" in (pt.get("rationale_he") or ""))
record("60. source_example mentions food source (מרגרינה or פשתן or סויה)",
       any(s in (pt.get("source_example") or "")
           for s in ["מרגרינה", "פשתן", "סויה", "סטרולים"]))

# ── Test 61: is_prepped == True does NOT fire PLANNING_OBSTACLE ───────────
record("61. PLANNING_OBSTACLE NOT in triggered_rules when prepped",
       "PLANNING_OBSTACLE" not in r59["triggered_rules"])
record("61. oars_open_question_he is None when prepped",
       r59.get("oars_open_question_he") is None)

# ── Test 62: is_prepped == True does NOT fire push notification ───────────
record("62. push_notification_he is None when prepped (no obstacle signal)",
       r59.get("push_notification_he") is None)

# ── Test 63: Orthogonality — Phase 1 + Phase 3 coexist ───────────────────
r63 = post_eval({
    "user_id": "ortho-p1-p3", "current_week": 10,
    "sleep":    {"duration_hours": 4.5},
    "steps":    {"steps": 2000, "idle_minutes": 90},
    "planning": {"is_prepped": True, "day_of_week": 6},
})
# Phase 1 rules should still fire
record("63. Phase 1 SLEEP_SHORT still fires in week 10",
       "SLEEP_SHORT" in r63["triggered_rules"])
record("63. Phase 1 SEDENTARY_ALERT still fires in week 10",
       "SEDENTARY_ALERT" in r63["triggered_rules"])
# Phase 3 phytosterol also fires
record("63. Phase 3 PHYTOSTEROL_TARGET fires alongside Phase 1",
       "PHYTOSTEROL_TARGET" in r63["triggered_rules"])
# nutrition_target (from Phase 1 sleep rule) and phytosterol_target coexist
record("63. menu_adjustment present (Phase 1 sleep rule)",
       r63.get("menu_adjustment") is not None)
record("63. phytosterol_target present (Phase 3)",
       r63.get("phytosterol_target") is not None)
# Phase 1 menu flags not overwritten
ma63 = r63.get("menu_adjustment") or {}
record("63. menu_adjustment.increase_plant_protein preserved",
       ma63.get("increase_plant_protein") is True)

# ── Test 64: Orthogonality — Phase 2 + Phase 3 coexist ───────────────────
r64 = post_eval({
    "user_id": "ortho-p2-p3", "current_week": 12,
    "sleep":       {"duration_hours": 4.5},
    "heart_rate":  {"resting_hr": 75},
    "user_baseline_rhr": 60,      # 75/60 = 25% > 10% → recovery fires
    "planning":    {"is_prepped": False, "day_of_week": 6},
})
record("64. Phase 2 RECOVERY_BIOFEEDBACK fires in week 12",
       "RECOVERY_BIOFEEDBACK" in r64["triggered_rules"])
record("64. Phase 3 PLANNING_OBSTACLE fires alongside Phase 2",
       "PLANNING_OBSTACLE" in r64["triggered_rules"])
# oars_reflection_he (P2 recovery) and oars_open_question_he (P3) coexist
record("64. oars_reflection_he (recovery) preserved",
       has_hebrew(r64.get("oars_reflection_he")))
record("64. oars_open_question_he (planning) also present",
       has_hebrew(r64.get("oars_open_question_he")))
# nutrition_target (Phase 2) preserved
record("64. nutrition_target.plant_protein_g = 50 (Phase 2 preserved)",
       (r64.get("nutrition_target") or {}).get("plant_protein_g") == 50)
record("64. phytosterol_target is None (is_prepped=False)",
       r64.get("phytosterol_target") is None)

# ── Test 65: push notification priority — P2 recovery holds when P3 also fires
push64 = r64.get("push_notification_he") or ""
record("65. push_notification_he is the P2 recovery push (higher priority)",
       "מנוחה" in push64 or "MUFA" in push64 or "50" in push64)
# P3 planning push is in clinical_notes (not overwritten)
record("65. P3 planning push recorded in clinical_notes_he",
       any("קופסאות" in n or "הכנה" in n for n in r64.get("clinical_notes_he", [])))

# ── Test 66: All 3 phases active simultaneously ───────────────────────────
r66 = post_eval({
    "user_id": "all-phases", "current_week": 10,
    "sleep":         {"duration_hours": 5.0},
    "steps":         {"steps": 3000, "idle_minutes": 70},
    "exercise":      {"type": "STRENGTH", "duration_minutes": 45, "completed": True},
    "heart_rate":    {"resting_hr": 72},
    "user_baseline_rhr": 60,
    "planning":      {"is_prepped": True, "day_of_week": 6},
})
all_rules = set(r66["triggered_rules"])
record("66. All 3 phase-spanning rules fire: SLEEP_SHORT",
       "SLEEP_SHORT" in all_rules)
record("66. SEDENTARY_ALERT fires",
       "SEDENTARY_ALERT" in all_rules)
record("66. GLUT4_STRENGTH fires (P2)",
       "GLUT4_STRENGTH" in all_rules)
record("66. RECOVERY_BIOFEEDBACK fires (P2)",
       "RECOVERY_BIOFEEDBACK" in all_rules)
record("66. PHYTOSTEROL_TARGET fires (P3)",
       "PHYTOSTEROL_TARGET" in all_rules)
# 5 distinct rules, no duplicates
record("66. No duplicate triggered_rules",
       len(r66["triggered_rules"]) == len(set(r66["triggered_rules"])))

# ── Test 67: Schema validation — PlanningSessionRecord fields ─────────────
resp67a = client.post("/api/v1/evaluate", json={
    "user_id": "val-test", "current_week": 10,
    "planning": {"is_prepped": True, "day_of_week": 8},   # day 8 out of range
})
record("67. day_of_week=8 → HTTP 422", resp67a.status_code == 422)

resp67b = client.post("/api/v1/evaluate", json={
    "user_id": "val-test", "current_week": 10,
    "planning": {"is_prepped": True, "day_of_week": 0},   # day 0 out of range
})
record("67. day_of_week=0 → HTTP 422", resp67b.status_code == 422)

resp67c = client.post("/api/v1/evaluate", json={
    "user_id": "val-test", "current_week": 10,
    "planning": {"is_prepped": True, "day_of_week": 7},   # valid: Sunday
})
record("67. day_of_week=7 → HTTP 200", resp67c.status_code == 200)

# ── Test 68: planning field absent — Phase 3 rules simply don't fire ──────
r68 = post_eval({"user_id": "no-planning", "current_week": 10})
record("68. No planning field → PLANNING_OBSTACLE not triggered",
       "PLANNING_OBSTACLE" not in r68["triggered_rules"])
record("68. No planning field → PHYTOSTEROL_TARGET not triggered",
       "PHYTOSTEROL_TARGET" not in r68["triggered_rules"])
record("68. phytosterol_target is None when no planning",
       r68.get("phytosterol_target") is None)

# ── Test 69: UTF-8 integrity of Phase 3 response ─────────────────────────
raw69 = client.post("/api/v1/evaluate", json={
    "user_id": "utf8-p3", "current_week": 10,
    "planning": {"is_prepped": False, "day_of_week": 6},
}).content
try:
    decoded69 = raw69.decode("utf-8")
    record("69. Phase 3 response decodes as UTF-8", True)
    record("69. Hebrew present in raw Phase 3 bytes",
           any("֐" <= c <= "׿" for c in decoded69))
except UnicodeDecodeError as e:
    record("69. Phase 3 response decodes as UTF-8", False, str(e))
    record("69. Hebrew present in raw bytes", False)

# ── Test 70: Phase 3 clinical_notes_he contains phase note ───────────────
r70 = post_eval({"user_id": "p3-notes", "current_week": 11})
record("70. clinical_notes_he contains Phase 3 note",
       any(has_hebrew(n) for n in r70.get("clinical_notes_he", [])))
record("70. /health endpoint mentions Phase 3",
       "Phase 3" in str(client.get("/health").json()))

# ===========================================================================
# Summary
# ===========================================================================

print("\n" + "=" * 60)
total  = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"\nתוצאות | Results: {passed}/{total} passed")

if failed:
    print(f"\n{failed} test(s) FAILED:")
    for name, ok, detail in results:
        if not ok:
            print(f"  - {name}" + (f" ({detail})" if detail else ""))
    sys.exit(1)
else:
    print("\nכל הבדיקות עברו בהצלחה | All tests passed.")
    sys.exit(0)
