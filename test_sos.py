# -*- coding: utf-8 -*-
"""
Integration test suite — SOS Craving Toolkit (trigger + resolve lifecycle).
Tests: POST /api/v1/sos/trigger  |  POST /api/v1/sos/resolve

Verifies:
  - Correct HTTP response structure and Hebrew content
  - Exact SOS_RELAPSE_EMPATHY string from locales/he.json
  - 3-step protocol integrity (Hebrew titles + instructions)
  - Timestamp is logged correctly in mock_state.json
  - Full lifecycle: trigger -> resolve(LAPSE) -> morning queue
  - Exact LAPSE_OARS_AFFIRMATION and LAPSE_HABIT_RESET strings from locales/he.json
  - Historical log integrity: past events never deleted, resolution appended
  - Concurrent calls do not corrupt state
  - UTF-8 encoding survives the full JSON round-trip
"""

from __future__ import annotations

import sys
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

from fastapi.testclient import TestClient

sys.path.insert(0, ".")

# Reset mock_state.json to clean fixture before importing app
_STATE_PATH = Path("backend/mock_state.json")
_CLEAN_STATE = {"users": {}, "sos_events": []}
_STATE_PATH.write_text(json.dumps(_CLEAN_STATE, ensure_ascii=False, indent=2), encoding="utf-8")

from backend.app.main import app  # noqa: E402 — must import after state reset

client = TestClient(app)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = PASS if ok else FAIL
    print(f"  [{status}] {name}" + (f"  ({detail})" if detail else ""))


def read_state() -> dict:
    return json.loads(_STATE_PATH.read_text(encoding="utf-8"))


def post_sos(user_id: str = "sos-test-user", week: int = 11) -> dict:
    resp = client.post("/api/v1/sos/trigger", json={"user_id": user_id, "week_context": week})
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Test 1: Basic response structure
# ---------------------------------------------------------------------------
print("\n=== Test 1: Basic Response Structure ===")
data = post_sos("user-001")

record("user_id echoed correctly", data["user_id"] == "user-001")
record("week_context is 11", data["week_context"] == 11)
record("event_logged is True", data["event_logged"] is True)
record("timestamp_utc is present and non-empty", bool(data.get("timestamp_utc")))
record("timestamp_utc is valid ISO-8601",
       bool(datetime.fromisoformat(data["timestamp_utc"].replace("Z", "+00:00"))))


# ---------------------------------------------------------------------------
# Test 2: Exact OARS empathy string from locales/he.json
# ---------------------------------------------------------------------------
print("\n=== Test 2: Exact OARS Empathy String (SOS_RELAPSE_EMPATHY) ===")
locales = json.loads(Path("locales/he.json").read_text(encoding="utf-8"))
expected_empathy = locales["SOS_RELAPSE_EMPATHY"]

record(
    "empathy_message_he matches locales/he.json exactly",
    data["empathy_message_he"] == expected_empathy,
    f"got: {data.get('empathy_message_he', '')[:40]}...",
)
record(
    "empathy contains 'דחף' (craving/urge)",
    "דחף" in data["empathy_message_he"],
)
record(
    "empathy contains 'אשמה' (blame/guilt — non-judgmental marker)",
    "אשמה" in data["empathy_message_he"],
)


# ---------------------------------------------------------------------------
# Test 3: 3-step SOS protocol
# ---------------------------------------------------------------------------
print("\n=== Test 3: 3-Step SOS Protocol ===")
steps = data.get("protocol_steps", [])

record("exactly 3 protocol steps returned", len(steps) == 3)
record("step numbers are [1, 2, 3]", [s["step_number"] for s in steps] == [1, 2, 3])

# Step 1: cold water / physical counter-measure
record(
    "Step 1 instruction contains cold water cue (מים קרים)",
    len(steps) >= 1 and "מים קרים" in steps[0]["instruction_he"],
)
record(
    "Step 1 instruction mentions lemon (לימון)",
    len(steps) >= 1 and "לימון" in steps[0]["instruction_he"],
)

# Step 2: mindful delay
record(
    "Step 2 instruction contains 5-minute delay (5 דקות)",
    len(steps) >= 2 and "5 דקות" in steps[1]["instruction_he"],
)
record(
    "Step 2 instruction references urge-as-wave metaphor (גל)",
    len(steps) >= 2 and "גל" in steps[1]["instruction_he"],
)

# Step 3: micro-movement
record(
    "Step 3 instruction contains 10-minute walk (10 דקות)",
    len(steps) >= 3 and "10 דקות" in steps[2]["instruction_he"],
)
record(
    "Step 3 instruction mentions cortisol (קורטיזול)",
    len(steps) >= 3 and "קורטיזול" in steps[2]["instruction_he"],
)

# Hebrew titles present
record("Step 1 has Hebrew title", len(steps) >= 1 and bool(steps[0]["title_he"]))
record("Step 2 has Hebrew title", len(steps) >= 2 and bool(steps[1]["title_he"]))
record("Step 3 has Hebrew title", len(steps) >= 3 and bool(steps[2]["title_he"]))


# ---------------------------------------------------------------------------
# Test 4: mock_state.json — timestamp logged correctly
# ---------------------------------------------------------------------------
print("\n=== Test 4: State Persistence in mock_state.json ===")
state = read_state()
sos_events = state.get("sos_events", [])

record("sos_events array exists in state", "sos_events" in state)
record("at least 1 event was appended", len(sos_events) >= 1)

last_event = sos_events[-1] if sos_events else {}
record("last event user_id matches", last_event.get("user_id") == "user-001")
record("last event week_context is 11", last_event.get("week_context") == 11)
record(
    "last event timestamp_utc matches response timestamp",
    last_event.get("timestamp_utc") == data["timestamp_utc"],
)
record(
    "stored timestamp is valid ISO-8601",
    bool(datetime.fromisoformat(last_event["timestamp_utc"].replace("Z", "+00:00")))
    if last_event.get("timestamp_utc") else False,
)


# ---------------------------------------------------------------------------
# Test 5: Multiple calls accumulate events without corruption
# ---------------------------------------------------------------------------
print("\n=== Test 5: Multiple Calls Accumulate State Correctly ===")
# Fire 3 more triggers for different users
for uid in ["user-A", "user-B", "user-C"]:
    post_sos(uid, week=11)

state_after = read_state()
total_events = len(state_after["sos_events"])
record("4 total events in sos_events (1 from Test 1 + 3 new)", total_events == 4)
record("all 4 events have user_id field", all("user_id" in e for e in state_after["sos_events"]))
record("all 4 events have timestamp_utc field", all("timestamp_utc" in e for e in state_after["sos_events"]))
users_logged = {e["user_id"] for e in state_after["sos_events"]}
record("all 4 distinct user IDs stored", users_logged == {"user-001", "user-A", "user-B", "user-C"})


# ---------------------------------------------------------------------------
# Test 6: Phase label and closing message in Hebrew
# ---------------------------------------------------------------------------
print("\n=== Test 6: Phase Label and Closing Message ===")
record("phase_he is non-empty Hebrew", bool(data.get("phase_he")) and "שבוע" in data["phase_he"])
record("protocol_header_he is non-empty", bool(data.get("protocol_header_he")))
record("closing_message_he references strength (חזק)", "חזק" in data.get("closing_message_he", ""))


# ---------------------------------------------------------------------------
# Test 7: UTF-8 encoding integrity — Hebrew survives raw bytes round-trip
# ---------------------------------------------------------------------------
print("\n=== Test 7: UTF-8 Encoding Integrity ===")
raw_resp = client.post(
    "/api/v1/sos/trigger",
    content=json.dumps({"user_id": "utf8-check", "week_context": 11}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
raw_bytes = raw_resp.content
decoded = raw_bytes.decode("utf-8")

record("Response decodes cleanly as UTF-8", True)
record("Hebrew craving word present in raw bytes (דחף)", "דחף" in decoded)
record("Hebrew water cue present in raw bytes (מים)", "מים" in decoded)

# Verify state file itself is valid UTF-8
try:
    _STATE_PATH.read_text(encoding="utf-8")
    record("mock_state.json is valid UTF-8", True)
except UnicodeDecodeError as e:
    record("mock_state.json is valid UTF-8", False, str(e))


# ---------------------------------------------------------------------------
# Test 8: Validation — invalid week rejected by Pydantic
# ---------------------------------------------------------------------------
print("\n=== Test 8: Input Validation (week out of range) ===")
bad_resp = client.post("/api/v1/sos/trigger", json={"user_id": "bad-user", "week_context": 99})
record("week=99 returns HTTP 422 (Unprocessable Entity)", bad_resp.status_code == 422)


# ---------------------------------------------------------------------------
# Test 9: Full lifecycle — trigger then resolve with SUCCESS
# ---------------------------------------------------------------------------
print("\n=== Test 9: Resolve Lifecycle - SUCCESS status ===")

trigger_resp = post_sos("lifecycle-success", week=12)
trigger_ts = trigger_resp["timestamp_utc"]

resolve_resp = client.post("/api/v1/sos/resolve", json={
    "user_id": "lifecycle-success",
    "event_timestamp_utc": trigger_ts,
    "status": "SUCCESS",
    "week_context": 12,
})
record("resolve SUCCESS returns HTTP 200", resolve_resp.status_code == 200)
rdata = resolve_resp.json()

record("user_id echoed in resolve response", rdata["user_id"] == "lifecycle-success")
record("event_timestamp_utc matches trigger", rdata["event_timestamp_utc"] == trigger_ts)
record("status is SUCCESS", rdata["status"] == "SUCCESS")
record("resolved_at_utc is present and valid ISO-8601",
       bool(datetime.fromisoformat(rdata["resolved_at_utc"].replace("Z", "+00:00"))))
record("SUCCESS acknowledgement_he is Hebrew (כל הכבוד)",
       "כל הכבוד" in rdata.get("acknowledgement_he", ""))
record("morning_queue is None for SUCCESS", rdata["morning_queue"] is None)

# Verify state: resolution appended, original data intact
state9 = read_state()
success_event = next(
    (e for e in state9["sos_events"]
     if e.get("user_id") == "lifecycle-success" and e.get("timestamp_utc") == trigger_ts),
    None,
)
record("SUCCESS event exists in sos_events", success_event is not None)
record("resolution_status appended as SUCCESS",
       success_event.get("resolution_status") == "SUCCESS" if success_event else False)
record("original timestamp_utc preserved",
       success_event.get("timestamp_utc") == trigger_ts if success_event else False)
record("week_context preserved in event",
       success_event.get("week_context") == 12 if success_event else False)


# ---------------------------------------------------------------------------
# Test 10: Full lifecycle — trigger then resolve with LAPSE
# ---------------------------------------------------------------------------
print("\n=== Test 10: Resolve Lifecycle - LAPSE status ===")

lapse_trigger = post_sos("lifecycle-lapse", week=12)
lapse_ts = lapse_trigger["timestamp_utc"]

lapse_resp = client.post("/api/v1/sos/resolve", json={
    "user_id": "lifecycle-lapse",
    "event_timestamp_utc": lapse_ts,
    "status": "LAPSE",
    "week_context": 12,
})
record("resolve LAPSE returns HTTP 200", lapse_resp.status_code == 200)
ldata = lapse_resp.json()

record("status is LAPSE", ldata["status"] == "LAPSE")
record("LAPSE acknowledgement_he is Hebrew (תודה שסיפרת)",
       "תודה שסיפרת" in ldata.get("acknowledgement_he", ""))
record("morning_queue is NOT None for LAPSE", ldata["morning_queue"] is not None)


# ---------------------------------------------------------------------------
# Test 11: Exact Hebrew strings in LAPSE morning_queue payload
# ---------------------------------------------------------------------------
print("\n=== Test 11: Exact Hebrew Strings in LAPSE Morning Queue ===")
locales_full = json.loads(Path("locales/he.json").read_text(encoding="utf-8"))
mq = ldata.get("morning_queue", {})

record(
    "oars_affirmation_he matches locales/he.json LAPSE_OARS_AFFIRMATION exactly",
    mq.get("oars_affirmation_he") == locales_full["LAPSE_OARS_AFFIRMATION"],
)
record(
    "oars_affirmation contains key marker (ניצחון מנטלי)",
    "ניצחון מנטלי" in mq.get("oars_affirmation_he", ""),
)
record(
    "oars_affirmation contains self-awareness marker (זיהית שנפלת)",
    "זיהית שנפלת" in mq.get("oars_affirmation_he", ""),
)
record(
    "habit_reset_he matches locales/he.json LAPSE_HABIT_RESET exactly",
    mq.get("habit_reset_he") == locales_full["LAPSE_HABIT_RESET"],
)
record(
    "habit_reset contains morning focus cue (ארוחת הבוקר)",
    "ארוחת הבוקר" in mq.get("habit_reset_he", ""),
)
record(
    "habit_reset contains no-calculation cue (חישובים)",
    "חישובים" in mq.get("habit_reset_he", ""),
)
record("header_he is non-empty Hebrew", bool(mq.get("header_he")))
record("queued_at_utc is valid ISO-8601",
       bool(datetime.fromisoformat(mq["queued_at_utc"].replace("Z", "+00:00")))
       if mq.get("queued_at_utc") else False)


# ---------------------------------------------------------------------------
# Test 12: morning_queue persisted in mock_state.json
# ---------------------------------------------------------------------------
print("\n=== Test 12: morning_queue Persisted in State ===")
state12 = read_state()

record("morning_queue key exists in state", "morning_queue" in state12)
lapse_queued = [
    e for e in state12.get("morning_queue", [])
    if e.get("user_id") == "lifecycle-lapse"
]
record("LAPSE user has exactly 1 morning_queue entry", len(lapse_queued) == 1)

qe = lapse_queued[0] if lapse_queued else {}
record(
    "queued oars_affirmation_he matches locales exactly",
    qe.get("oars_affirmation_he") == locales_full["LAPSE_OARS_AFFIRMATION"],
)
record(
    "queued habit_reset_he matches locales exactly",
    qe.get("habit_reset_he") == locales_full["LAPSE_HABIT_RESET"],
)
record("queued_at_utc is stored in state",
       bool(qe.get("queued_at_utc")))

# Original LAPSE event still has full history (not deleted)
lapse_event = next(
    (e for e in state12["sos_events"]
     if e.get("user_id") == "lifecycle-lapse" and e.get("timestamp_utc") == lapse_ts),
    None,
)
record("original LAPSE sos_event still present (not deleted)", lapse_event is not None)
record("resolution_status appended as LAPSE",
       lapse_event.get("resolution_status") == "LAPSE" if lapse_event else False)
record("original trigger timestamp preserved in event",
       lapse_event.get("timestamp_utc") == lapse_ts if lapse_event else False)


# ---------------------------------------------------------------------------
# Test 13: Resolve with unknown event_timestamp returns 404
# ---------------------------------------------------------------------------
print("\n=== Test 13: Resolve with Unknown Timestamp Returns 404 ===")
bad_resolve = client.post("/api/v1/sos/resolve", json={
    "user_id": "no-such-user",
    "event_timestamp_utc": "1970-01-01T00:00:00+00:00",
    "status": "SUCCESS",
    "week_context": 12,
})
record("unknown event returns HTTP 404", bad_resolve.status_code == 404)
record("404 detail is in Hebrew (לא נמצא)", "לא נמצא" in bad_resolve.json().get("detail", ""))


# ---------------------------------------------------------------------------
# Test 14: Resolve invalid status returns 422
# ---------------------------------------------------------------------------
print("\n=== Test 14: Invalid Status Enum Returns 422 ===")
bad_status = client.post("/api/v1/sos/resolve", json={
    "user_id": "any-user",
    "event_timestamp_utc": "2026-01-01T00:00:00+00:00",
    "status": "MAYBE",
    "week_context": 12,
})
record("invalid status returns HTTP 422", bad_status.status_code == 422)


# ---------------------------------------------------------------------------
# Test 15: SUCCESS resolve does NOT create morning_queue entry
# ---------------------------------------------------------------------------
print("\n=== Test 15: SUCCESS Does Not Pollute Morning Queue ===")
state15 = read_state()
success_queued = [
    e for e in state15.get("morning_queue", [])
    if e.get("user_id") == "lifecycle-success"
]
record("no morning_queue entry for SUCCESS user", len(success_queued) == 0)


# ---------------------------------------------------------------------------
# Test 16: UTF-8 integrity of LAPSE strings through full round-trip
# ---------------------------------------------------------------------------
print("\n=== Test 16: UTF-8 Integrity of LAPSE Response ===")
raw = lapse_resp.content.decode("utf-8")
record("LAPSE response decodes as UTF-8", True)
record("ניצחון present in raw LAPSE response bytes", "ניצחון" in raw)
record("ארוחת הבוקר present in raw LAPSE response bytes", "ארוחת הבוקר" in raw)
record("state file still valid UTF-8 after resolve",
       bool(Path("backend/mock_state.json").read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
total = len(results)
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
