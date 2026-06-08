# -*- coding: utf-8 -*-
"""
test_content_curation.py — Content Curation & Deep Linking QA

Tests that action_url / action_label are correctly attached to
EvaluationResponse by the clinical rules engine, and that the
FastAPI endpoint exposes them in the JSON response.

Scenarios:
  1.  Schema: EvaluationResponse has action_url field (Optional[str])
  2.  Schema: EvaluationResponse has action_label field (Optional[str])
  3.  Schema: Both fields default to None
  4.  Schema: action_url accepts valid URL string
  5.  Schema: action_label accepts Hebrew string

  6.  Rule P2-1 (GLUT4 STRENGTH): action_url is YouTube URL
  7.  Rule P2-1 (GLUT4 STRENGTH): action_url starts with https://
  8.  Rule P2-1 (GLUT4 STRENGTH): action_url contains 'youtube'
  9.  Rule P2-1 (GLUT4 STRENGTH): action_label is Hebrew (non-empty)
  10. Rule P2-1 (GLUT4 STRENGTH): action_label sourced from locales/he.json

  11. Rule P2-1 (CARDIO): action_url is None (no URL for cardio)
  12. Rule P2-1 (STRENGTH not completed): action_url is None

  13. Rule P2-2 (Recovery biofeedback): action_url is recipe URL
  14. Rule P2-2 (Recovery biofeedback): action_url starts with https://
  15. Rule P2-2 (Recovery): action_label is Hebrew (non-empty)
  16. Rule P2-2 (Recovery): action_label differs from GLUT4 label

  17. Cascade (STRENGTH + Recovery both fire): GLUT4 URL wins (higher priority)
  18. No rules fire: action_url is None, action_label is None

  19. Rule P3-2 (Phytosterol): action_url is recipe URL
  20. Rule P3-2 (Phytosterol): action_url starts with https://
  21. Rule P3-2 (Phytosterol): action_label is Hebrew (non-empty)
  22. Rule P3-2 (Phytosterol): action_label sourced from locales/he.json key

  23. FastAPI endpoint: GLUT4 payload → action_url in JSON response
  24. FastAPI endpoint: GLUT4 payload → action_label in JSON response
  25. FastAPI endpoint: Recovery payload → action_url in JSON response
  26. FastAPI endpoint: No-trigger payload → action_url is null in JSON
  27. FastAPI endpoint: Phase 3 phytosterol → action_url in JSON response

  28. URL integrity: no action_url is an empty string
  29. URL integrity: no action_label is an empty string
  30. Locale key ACTION_STRENGTH_YOUTUBE_LABEL present in he.json
  31. Locale key ACTION_RECOVERY_RECIPE_LABEL present in he.json
  32. Locale key ACTION_PHYTOSTEROL_RECIPE_LABEL present in he.json
"""

import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, ".")

# ── Fixture: reset mock_state for predictable baseline lookups ────────────
_STATE_PATH = Path("backend/mock_state.json")
_CLEAN_STATE = {
    "users": {},
    "sos_events": [],
    "morning_queue": [],
    "user_baselines": {
        "cc-test-001": {"baseline_rhr": 60},
    },
    "notifications_log": [],
}
_STATE_PATH.write_text(json.dumps(_CLEAN_STATE, ensure_ascii=False, indent=2), encoding="utf-8")

from backend.app.main import app

client = TestClient(app)

# ── Helpers ───────────────────────────────────────────────────────────────

passed = 0
failed = 0
_failures = []


def ok(condition: bool, num: int, desc: str) -> None:
    global passed, failed
    if condition:
        print(f"  ✓ [{num:02d}] {desc}")
        passed += 1
    else:
        print(f"  ✗ [{num:02d}] {desc}")
        _failures.append((num, desc))
        failed += 1


def _eval(payload: dict) -> dict:
    r = client.post("/api/v1/evaluate", json=payload)
    assert r.status_code == 200, f"Unexpected {r.status_code}: {r.text}"
    return r.json()


# ── Load locales directly for assertions ─────────────────────────────────
_LOCALES = json.loads(Path("locales/he.json").read_text(encoding="utf-8"))

# ── Payloads ──────────────────────────────────────────────────────────────

STRENGTH_PAYLOAD = {
    "user_id": "cc-test-001",
    "current_week": 6,
    "exercise": {"type": "STRENGTH", "duration_minutes": 45, "completed": True},
}

CARDIO_PAYLOAD = {
    "user_id": "cc-test-001",
    "current_week": 6,
    "exercise": {"type": "CARDIO", "duration_minutes": 30, "completed": True},
}

STRENGTH_NOT_COMPLETED_PAYLOAD = {
    "user_id": "cc-test-001",
    "current_week": 6,
    "exercise": {"type": "STRENGTH", "duration_minutes": 45, "completed": False},
}

RECOVERY_PAYLOAD = {
    "user_id": "cc-test-001",
    "current_week": 6,
    "heart_rate": {"resting_hr": 72},   # 72 > 60 * 1.10 = 66 → elevated
    "sleep":      {"duration_hours": 5.0},
}

STRENGTH_AND_RECOVERY_PAYLOAD = {
    "user_id": "cc-test-001",
    "current_week": 6,
    "exercise":   {"type": "STRENGTH", "duration_minutes": 45, "completed": True},
    "heart_rate": {"resting_hr": 72},
    "sleep":      {"duration_hours": 5.0},
}

NO_TRIGGER_PAYLOAD = {
    "user_id": "cc-test-001",
    "current_week": 6,
    "sleep": {"duration_hours": 7.5},
    "steps": {"steps": 9000, "idle_minutes": 20},
}

PHYTOSTEROL_PAYLOAD = {
    "user_id": "cc-test-001",
    "current_week": 11,
    "planning": {"is_prepped": True, "day_of_week": 6},
}

# ── Group 1: Schema ────────────────────────────────────────────────────────

print("\n── Group 1: Schema ──")
from backend.app.schemas import EvaluationResponse

r = EvaluationResponse(user_id="x", current_week=1, phase="test")
ok(hasattr(r, "action_url"),       1,  "EvaluationResponse has action_url field")
ok(hasattr(r, "action_label"),     2,  "EvaluationResponse has action_label field")
ok(r.action_url is None,           3,  "action_url defaults to None")
ok(r.action_label is None,         4,  "action_label defaults to None")

r2 = EvaluationResponse(user_id="x", current_week=1, phase="t",
                        action_url="https://example.com", action_label="לחץ כאן")
ok(r2.action_url == "https://example.com", 4, "action_url accepts URL string")
ok(r2.action_label == "לחץ כאן",          5, "action_label accepts Hebrew string")

# ── Group 2: Rule P2-1 GLUT4 STRENGTH ────────────────────────────────────

print("\n── Group 2: Rule P2-1 GLUT4 STRENGTH ──")
s = _eval(STRENGTH_PAYLOAD)
ok(s.get("action_url") is not None,            6,  "GLUT4 STRENGTH: action_url is set")
ok(s["action_url"].startswith("https://"),     7,  "GLUT4 STRENGTH: action_url starts with https://")
ok("youtube" in s["action_url"].lower(),       8,  "GLUT4 STRENGTH: action_url contains 'youtube'")
ok(bool(s.get("action_label")),                9,  "GLUT4 STRENGTH: action_label is non-empty")

expected_label = _LOCALES.get("ACTION_STRENGTH_YOUTUBE_LABEL", "")
ok(s["action_label"] == expected_label,        10, "GLUT4 STRENGTH: action_label matches locales key")

# ── Group 3: No URL cases ─────────────────────────────────────────────────

print("\n── Group 3: No-URL cases ──")
c = _eval(CARDIO_PAYLOAD)
ok(c.get("action_url") is None,                11, "CARDIO: action_url is None (no URL for cardio)")

snc = _eval(STRENGTH_NOT_COMPLETED_PAYLOAD)
ok(snc.get("action_url") is None,              12, "STRENGTH not completed: action_url is None")

# ── Group 4: Rule P2-2 Recovery ──────────────────────────────────────────

print("\n── Group 4: Rule P2-2 Recovery ──")
rec = _eval(RECOVERY_PAYLOAD)
ok(rec.get("action_url") is not None,          13, "Recovery: action_url is set")
ok(rec["action_url"].startswith("https://"),   14, "Recovery: action_url starts with https://")
ok(bool(rec.get("action_label")),              15, "Recovery: action_label is non-empty")
ok(rec["action_label"] != s["action_label"],   16, "Recovery: action_label differs from GLUT4 label")

# ── Group 5: Cascade ─────────────────────────────────────────────────────

print("\n── Group 5: Cascade (STRENGTH + Recovery) ──")
both = _eval(STRENGTH_AND_RECOVERY_PAYLOAD)
ok("GLUT4_STRENGTH"      in both["triggered_rules"], 17, "Cascade: GLUT4_STRENGTH in triggered_rules")
ok("RECOVERY_BIOFEEDBACK" in both["triggered_rules"], 17, "Cascade: RECOVERY_BIOFEEDBACK in triggered_rules")
ok("youtube" in both["action_url"].lower(),           17, "Cascade: GLUT4 YouTube URL wins over recovery recipe")

# ── Group 6: No trigger ───────────────────────────────────────────────────

print("\n── Group 6: No trigger ──")
nt = _eval(NO_TRIGGER_PAYLOAD)
ok(nt.get("action_url")   is None, 18, "No trigger: action_url is None")
ok(nt.get("action_label") is None, 18, "No trigger: action_label is None")

# ── Group 7: Rule P3-2 Phytosterol ───────────────────────────────────────

print("\n── Group 7: Rule P3-2 Phytosterol ──")
phy = _eval(PHYTOSTEROL_PAYLOAD)
ok(phy.get("action_url") is not None,          19, "Phytosterol: action_url is set")
ok(phy["action_url"].startswith("https://"),   20, "Phytosterol: action_url starts with https://")
ok(bool(phy.get("action_label")),              21, "Phytosterol: action_label is non-empty")

expected_phy_label = _LOCALES.get("ACTION_PHYTOSTEROL_RECIPE_LABEL", "")
ok(phy["action_label"] == expected_phy_label,  22, "Phytosterol: action_label matches locale key")

# ── Group 8: FastAPI endpoint JSON shape ──────────────────────────────────

print("\n── Group 8: FastAPI JSON shape ──")
ok("action_url"   in s,     23, "FastAPI GLUT4: action_url key in JSON response")
ok("action_label" in s,     24, "FastAPI GLUT4: action_label key in JSON response")
ok("action_url"   in rec,   25, "FastAPI Recovery: action_url key in JSON response")
ok(nt["action_url"] is None, 26, "FastAPI no-trigger: action_url is null in JSON")
ok("action_url"   in phy,   27, "FastAPI Phytosterol: action_url key in JSON response")

# ── Group 9: URL / label integrity ───────────────────────────────────────

print("\n── Group 9: URL & label integrity ──")
for payload, tag in [(s, "GLUT4"), (rec, "Recovery"), (phy, "Phytosterol")]:
    url   = payload.get("action_url", "")
    label = payload.get("action_label", "")
    ok(url   != "",  28, f"{tag}: action_url is not empty string")
    ok(label != "",  29, f"{tag}: action_label is not empty string")

# ── Group 10: Locale keys present ─────────────────────────────────────────

print("\n── Group 10: Locale key presence ──")
ok("ACTION_STRENGTH_YOUTUBE_LABEL"   in _LOCALES, 30, "he.json has ACTION_STRENGTH_YOUTUBE_LABEL")
ok("ACTION_RECOVERY_RECIPE_LABEL"    in _LOCALES, 31, "he.json has ACTION_RECOVERY_RECIPE_LABEL")
ok("ACTION_PHYTOSTEROL_RECIPE_LABEL" in _LOCALES, 32, "he.json has ACTION_PHYTOSTEROL_RECIPE_LABEL")

# ── Summary ───────────────────────────────────────────────────────────────

total = passed + failed
print(f"\n{'═'*60}")
print(f"  Content Curation QA — {passed}/{total} assertions passed")
if _failures:
    print("\n  FAILURES:")
    for n, d in _failures:
        print(f"    ✗ [{n:02d}] {d}")
    sys.exit(1)
else:
    print("  All assertions passed ✓")
    sys.exit(0)
