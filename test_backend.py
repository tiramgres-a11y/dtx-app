# -*- coding: utf-8 -*-
"""
Standalone test suite for the DTx Backend Orchestrator — Phase 1 (Weeks 1-4: Reset).

Tests use FastAPI's TestClient (no live server required).
All Hebrew string assertions use exact substring matching to be resilient
to minor template edits while still catching encoding regressions.
"""

from __future__ import annotations

import sys
import json
from fastapi.testclient import TestClient

sys.path.insert(0, ".")
from backend.app.main import app

client = TestClient(app)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = PASS if ok else FAIL
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def post_evaluate(payload: dict) -> dict:
    resp = client.post("/api/v1/evaluate", json=payload)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Test 1: Health check
# ---------------------------------------------------------------------------

print("\n=== Test 1: Health Check ===")
r = client.get("/health")
record("GET /health returns 200", r.status_code == 200)
record("health response contains 'ok'", r.json().get("status") == "ok")


# ---------------------------------------------------------------------------
# Test 2: Low sleep (<6h) — sleep rule fires
# ---------------------------------------------------------------------------

print("\n=== Test 2: Low Sleep Rule (< 6.0 hours) ===")
payload = {
    "user_id": "test-user-001",
    "current_week": 2,
    "sleep": {"duration_hours": 4.5},
    "steps": {"steps": 3000, "idle_minutes": 30},
    "strength": {"logged": False},
}
data = post_evaluate(payload)

record("SLEEP_SHORT in triggered_rules", "SLEEP_SHORT" in data["triggered_rules"])
record("menu_adjustment is not null", data["menu_adjustment"] is not None)
record("menu: reduce_complex_carbs=True", data["menu_adjustment"]["reduce_complex_carbs"] is True)
record("menu: increase_plant_protein=True", data["menu_adjustment"]["increase_plant_protein"] is True)
record("menu: increase_nuts=True", data["menu_adjustment"]["increase_nuts"] is True)
record(
    "oars_reflection_he contains Hebrew sleep text",
    data["oars_reflection_he"] is not None
    and "שינה" in data["oars_reflection_he"],
)
record(
    "oars_reflection contains non-judgmental tone (מובן)",
    data["oars_reflection_he"] is not None
    and "מובן" in data["oars_reflection_he"],
)
record(
    "menu rationale_he is Hebrew (אינסולין)",
    "אינסולין" in data["menu_adjustment"]["rationale_he"],
)
record("push_notification_he is None (no sedentary)", data["push_notification_he"] is None)
record("strength_validation_he is None", data["strength_validation_he"] is None)


# ---------------------------------------------------------------------------
# Test 3: Adequate sleep (>= 6h) — sleep rule does NOT fire
# ---------------------------------------------------------------------------

print("\n=== Test 3: Adequate Sleep (>= 6.0 hours) - rule must NOT fire ===")
payload = {
    "user_id": "test-user-002",
    "current_week": 1,
    "sleep": {"duration_hours": 7.5},
    "steps": {"steps": 8000, "idle_minutes": 20},
}
data = post_evaluate(payload)

record("SLEEP_SHORT NOT in triggered_rules", "SLEEP_SHORT" not in data["triggered_rules"])
record("menu_adjustment is None", data["menu_adjustment"] is None)
record("oars_reflection_he is None", data["oars_reflection_he"] is None)


# ---------------------------------------------------------------------------
# Test 4: Sedentary rule (idle_minutes >= 60)
# ---------------------------------------------------------------------------

print("\n=== Test 4: Sedentary Rule (idle_minutes >= 60) ===")
payload = {
    "user_id": "test-user-003",
    "current_week": 3,
    "steps": {"steps": 1500, "idle_minutes": 90},
}
data = post_evaluate(payload)

record("SEDENTARY_ALERT in triggered_rules", "SEDENTARY_ALERT" in data["triggered_rules"])
record("push_notification_he is not None", data["push_notification_he"] is not None)
record(
    "push notification contains Hebrew movement cue (תנועה or עמוד)",
    data["push_notification_he"] is not None
    and ("תנועה" in data["push_notification_he"] or "עמוד" in data["push_notification_he"]),
)
record(
    "push notification contains glucose reference (סוכר)",
    data["push_notification_he"] is not None
    and "סוכר" in data["push_notification_he"],
)


# ---------------------------------------------------------------------------
# Test 5: Sedentary rule boundary — exactly 59 minutes (must NOT fire)
# ---------------------------------------------------------------------------

print("\n=== Test 5: Sedentary Boundary (idle_minutes=59) - rule must NOT fire ===")
payload = {
    "user_id": "test-user-004",
    "current_week": 1,
    "steps": {"steps": 2000, "idle_minutes": 59},
}
data = post_evaluate(payload)

record("SEDENTARY_ALERT NOT in triggered_rules", "SEDENTARY_ALERT" not in data["triggered_rules"])
record("push_notification_he is None", data["push_notification_he"] is None)


# ---------------------------------------------------------------------------
# Test 6: Strength workout logged
# ---------------------------------------------------------------------------

print("\n=== Test 6: Strength Workout Rule ===")
payload = {
    "user_id": "test-user-005",
    "current_week": 4,
    "strength": {"logged": True, "duration_minutes": 45},
}
data = post_evaluate(payload)

record("STRENGTH_LOGGED in triggered_rules", "STRENGTH_LOGGED" in data["triggered_rules"])
record("strength_validation_he is not None", data["strength_validation_he"] is not None)
record(
    "strength validation contains clinical window text (השרירים שלך עכשיו פתוחים)",
    data["strength_validation_he"] is not None
    and "השרירים שלך עכשיו פתוחים" in data["strength_validation_he"],
)
record(
    "strength validation references insulin window (גלוקוז)",
    data["strength_validation_he"] is not None
    and "גלוקוז" in data["strength_validation_he"],
)


# ---------------------------------------------------------------------------
# Test 7: All three rules fire simultaneously
# ---------------------------------------------------------------------------

print("\n=== Test 7: All Three Rules Fire Together ===")
payload = {
    "user_id": "test-user-006",
    "current_week": 2,
    "sleep": {"duration_hours": 5.0},
    "steps": {"steps": 1200, "idle_minutes": 120},
    "strength": {"logged": True, "duration_minutes": 30},
}
data = post_evaluate(payload)

record("All 3 rules triggered", set(data["triggered_rules"]) == {"SLEEP_SHORT", "SEDENTARY_ALERT", "STRENGTH_LOGGED"})
record("menu_adjustment present", data["menu_adjustment"] is not None)
record("oars_reflection_he present", data["oars_reflection_he"] is not None)
record("push_notification_he present", data["push_notification_he"] is not None)
record("strength_validation_he present", data["strength_validation_he"] is not None)
record("clinical_notes_he has 4 entries (1 phase note + 3 rule notes)", len(data["clinical_notes_he"]) == 4)


# ---------------------------------------------------------------------------
# Test 8: Phase routing — week 5 now routes to Phase 2 (not 501)
# (Updated: Phase 2 was implemented after this test was originally written)
# ---------------------------------------------------------------------------

print("\n=== Test 8: Phase Guard (week 5 -> Phase 2, week 14 -> 422) ===")
resp5 = client.post("/api/v1/evaluate", json={
    "user_id": "test-user-007",
    "current_week": 5,
})
record("Week 5 returns HTTP 200 (routes to Phase 2)", resp5.status_code == 200)
record("Week 5 response contains Phase 2 label", "שלב 2" in resp5.json().get("phase", ""))

# Week 14 is beyond the program scope → rejected by Pydantic schema (le=13)
resp14 = client.post("/api/v1/evaluate", json={
    "user_id": "test-user-007b",
    "current_week": 14,
})
record("Week 14 returns HTTP 422 (schema le=13)", resp14.status_code == 422)


# ---------------------------------------------------------------------------
# Test 9: UTF-8 encoding integrity — Hebrew survives JSON round-trip
# ---------------------------------------------------------------------------

print("\n=== Test 9: UTF-8 Encoding Integrity ===")
payload = {
    "user_id": "test-user-008",
    "current_week": 1,
    "sleep": {"duration_hours": 3.0},
    "steps": {"steps": 500, "idle_minutes": 75},
    "strength": {"logged": True},
}
raw_resp = client.post("/api/v1/evaluate", content=json.dumps(payload).encode("utf-8"),
                       headers={"Content-Type": "application/json"})
raw_bytes = raw_resp.content
decoded = raw_bytes.decode("utf-8")
record("Response decodes cleanly as UTF-8", True)
record(
    "Hebrew chars present in raw response bytes",
    "שינה" in decoded or "תנועה" in decoded or "שרירים" in decoded,
)


# ---------------------------------------------------------------------------
# Results summary
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"\nתוצאות | Results: {passed}/{total} passed")

if failed:
    print(f"\n❌ {failed} test(s) FAILED:")
    for name, ok, detail in results:
        if not ok:
            print(f"   - {name}" + (f" ({detail})" if detail else ""))
    sys.exit(1)
else:
    print("\n✅ כל הבדיקות עברו בהצלחה | All tests passed.")
    sys.exit(0)
