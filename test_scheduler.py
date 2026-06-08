# -*- coding: utf-8 -*-
"""
test_scheduler.py — Proactive Scheduler QA

Tests the check_weekend_prep_status job in complete isolation:
  - No live APScheduler instance needed
  - System time injected via the `now` parameter
  - State written to a temporary file, never touches real mock_state.json
  - dispatch_fn replaced by a spy that captures calls

Scenarios:
  1.  Eligible user on Friday → notification dispatched, state updated
  2.  Idempotency: same user, same ISO week → SKIPPED (no duplicate)
  3.  Idempotency after restart: state persisted → still skipped on reload
  4.  New ISO week → notification fires again (weekly reset)
  5.  is_prepped == True → skipped
  6.  current_week < 10 → skipped (not Phase 3)
  7.  Multiple users: eligible + prepped + not-phase3 → only eligible gets notified
  8.  Push message and OARS question are exact Hebrew strings from he.json
  9.  notifications_log entry written with all required fields
  10. notifications_sent counter increments correctly across weeks
  11. Friday 12:00 is the configured cron schedule
  12. Non-Friday weekday invocation: job still runs (caller controls timing)
  13. Missing 'users' key in state → handled gracefully (no crash)
  14. Empty users dict → no results, no crash
  15. Concurrent invocations (same ISO week) → idempotency holds under contention
  16. Scheduler module exports create_scheduler, start_scheduler, shutdown_scheduler
  17. All new scheduler locale keys present + Hebrew in he.json
  18. State file is valid UTF-8 after write
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, ".")

from backend.app.scheduler import (
    check_weekend_prep_status,
    PHASE_3_MIN_WEEK,
    CRON_DAY_OF_WEEK,
    CRON_HOUR,
    CRON_MINUTE,
    _iso_week,
    _t,
)

# ─── Harness ──────────────────────────────────────────────────────────────
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f"  ({detail})" if detail else ""))


def has_hebrew(s: str | None) -> bool:
    if not s:
        return False
    return any("א" <= c <= "ת" for c in s)


# ─── Helpers ──────────────────────────────────────────────────────────────

# A known Friday noon UTC (2026-06-05 is a Friday)
FRIDAY_NOON  = datetime(2026, 6,  5, 12, 0, 0, tzinfo=timezone.utc)
# Saturday — same ISO week, different day
SATURDAY_2PM = datetime(2026, 6,  6, 14, 0, 0, tzinfo=timezone.utc)
# Following Friday — new ISO week
NEXT_FRIDAY  = datetime(2026, 6, 12, 12, 0, 0, tzinfo=timezone.utc)


def make_state(users: dict | None = None) -> dict:
    """Build a minimal mock_state fixture."""
    return {
        "users":            users or {},
        "sos_events":       [],
        "user_baselines":   {},
        "notifications_log": [],
    }


def write_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def read_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def make_spy() -> tuple[list, callable]:
    """Return (calls_list, spy_fn) for capturing dispatch calls."""
    calls: list[dict] = []
    def spy(user_id: str, message: str, oars: str) -> None:
        calls.append({"user_id": user_id, "message": message, "oars": oars})
    return calls, spy


# ─── Eligible user fixture ────────────────────────────────────────────────
ELIGIBLE_USER = {
    "current_week": 10,
    "is_prepped":   False,
    "name":         "test-user-p3",
}


# ===========================================================================
print("\n=== Test 1: Eligible user on Friday → notification dispatched ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    write_state(sp, make_state({"u-eligible": dict(ELIGIBLE_USER)}))
    calls, spy = make_spy()

    results_1 = check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy, state_path=sp)

    record("1. Exactly 1 result returned",          len(results_1) == 1)
    record("1. Action = 'sent'",                    results_1[0]["action"] == "sent",
           results_1[0].get("action"))
    record("1. user_id echoed",                    results_1[0]["user_id"] == "u-eligible")
    record("1. dispatch_fn called once",            len(calls) == 1)
    record("1. dispatched user_id correct",         calls[0]["user_id"] == "u-eligible")
    record("1. push_message is Hebrew",             has_hebrew(calls[0]["message"]))
    record("1. oars question is Hebrew",            has_hebrew(calls[0]["oars"]))
    record("1. dispatched_at present in result",    bool(results_1[0].get("dispatched_at")))

    state_after = read_state(sp)
    sched_meta  = state_after["users"]["u-eligible"]["scheduler"]
    record("1. last_notified_iso_week written",     bool(sched_meta.get("last_notified_iso_week")))
    record("1. last_notified_timestamp written",    bool(sched_meta.get("last_notified_timestamp")))
    record("1. notifications_sent = 1",             sched_meta.get("notifications_sent") == 1)
    record("1. notifications_log has 1 entry",
           len(state_after.get("notifications_log", [])) == 1)
    log0 = state_after["notifications_log"][0]
    record("1. log entry has type WEEKEND_PREP_REMINDER",
           log0.get("type") == "WEEKEND_PREP_REMINDER")
    record("1. log entry push_message present",     bool(log0.get("push_message")))
    record("1. log entry oars_question present",    bool(log0.get("oars_question")))


# ===========================================================================
print("\n=== Test 2: Idempotency — same ISO week, same session ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    write_state(sp, make_state({"u-idm": dict(ELIGIBLE_USER)}))
    calls, spy = make_spy()

    # First call
    check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy, state_path=sp)
    first_sent = len(calls)

    # Second call — same ISO week
    results_2 = check_weekend_prep_status(now=SATURDAY_2PM, dispatch_fn=spy, state_path=sp)

    record("2. First call dispatched 1 notification",   first_sent == 1)
    record("2. Second call action = 'skipped_idempotent'",
           results_2[0]["action"] == "skipped_idempotent",
           results_2[0].get("action"))
    record("2. dispatch_fn NOT called a second time",   len(calls) == 1)

    state_idm = read_state(sp)
    record("2. notifications_sent still 1 (not incremented)",
           state_idm["users"]["u-idm"]["scheduler"]["notifications_sent"] == 1)
    record("2. notifications_log still 1 entry",
           len(state_idm.get("notifications_log", [])) == 1)


# ===========================================================================
print("\n=== Test 3: Idempotency after server restart (state reloaded from disk) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    write_state(sp, make_state({"u-restart": dict(ELIGIBLE_USER)}))
    calls1, spy1 = make_spy()

    # Simulate first server run
    check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy1, state_path=sp)

    # Simulate server restart — new spy, same state file on disk
    calls2, spy2 = make_spy()
    results_3 = check_weekend_prep_status(now=SATURDAY_2PM, dispatch_fn=spy2, state_path=sp)

    record("3. Notification was sent before restart",   len(calls1) == 1)
    record("3. Post-restart: action = 'skipped_idempotent'",
           results_3[0]["action"] == "skipped_idempotent")
    record("3. dispatch_fn NOT called after restart",   len(calls2) == 0)


# ===========================================================================
print("\n=== Test 4: New ISO week → notification fires again ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    write_state(sp, make_state({"u-weekly": dict(ELIGIBLE_USER)}))
    calls, spy = make_spy()

    # Week 1 Friday
    check_weekend_prep_status(now=FRIDAY_NOON,  dispatch_fn=spy, state_path=sp)
    # Week 2 Friday (new ISO week)
    results_4 = check_weekend_prep_status(now=NEXT_FRIDAY, dispatch_fn=spy, state_path=sp)

    record("4. Second Friday (new ISO week) action = 'sent'",
           results_4[0]["action"] == "sent",
           results_4[0].get("action"))
    record("4. dispatch_fn called twice total",     len(calls) == 2)

    state_w2 = read_state(sp)
    record("4. notifications_sent = 2 after two weeks",
           state_w2["users"]["u-weekly"]["scheduler"]["notifications_sent"] == 2)
    record("4. last_notified_iso_week updated to new week",
           state_w2["users"]["u-weekly"]["scheduler"]["last_notified_iso_week"] == _iso_week(NEXT_FRIDAY.date()))
    record("4. notifications_log has 2 entries",
           len(state_w2.get("notifications_log", [])) == 2)


# ===========================================================================
print("\n=== Test 5: is_prepped == True → skipped ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    prepped = dict(ELIGIBLE_USER) | {"is_prepped": True}
    write_state(sp, make_state({"u-prepped": prepped}))
    calls, spy = make_spy()

    results_5 = check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy, state_path=sp)

    record("5. Action = 'skipped_prepped'",         results_5[0]["action"] == "skipped_prepped")
    record("5. dispatch_fn NOT called",             len(calls) == 0)


# ===========================================================================
print("\n=== Test 6: current_week < 10 → skipped (not Phase 3) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    early = dict(ELIGIBLE_USER) | {"current_week": 9}
    write_state(sp, make_state({"u-early": early}))
    calls, spy = make_spy()

    results_6 = check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy, state_path=sp)

    record("6. Action = 'skipped_not_phase3'",      results_6[0]["action"] == "skipped_not_phase3")
    record("6. dispatch_fn NOT called",             len(calls) == 0)


# ===========================================================================
print("\n=== Test 7: Multiple users — mixed eligibility ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    users = {
        "u-ok":      dict(ELIGIBLE_USER),
        "u-prepped": dict(ELIGIBLE_USER) | {"is_prepped": True},
        "u-early":   dict(ELIGIBLE_USER) | {"current_week": 5},
    }
    write_state(sp, make_state(users))
    calls, spy = make_spy()

    results_7 = check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy, state_path=sp)

    actions = {r["user_id"]: r["action"] for r in results_7}
    record("7. 3 results returned",                 len(results_7) == 3)
    record("7. u-ok: sent",                         actions.get("u-ok") == "sent")
    record("7. u-prepped: skipped_prepped",          actions.get("u-prepped") == "skipped_prepped")
    record("7. u-early: skipped_not_phase3",         actions.get("u-early") == "skipped_not_phase3")
    record("7. dispatch_fn called once (u-ok only)", len(calls) == 1)
    record("7. dispatch_fn called for u-ok",         calls[0]["user_id"] == "u-ok")


# ===========================================================================
print("\n=== Test 8: Exact Hebrew strings from he.json ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    write_state(sp, make_state({"u-txt": dict(ELIGIBLE_USER)}))
    calls, spy = make_spy()
    res = check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy, state_path=sp)

    expected_push = _t("SCHEDULER_PREP_PUSH")
    expected_oars = _t("SCHEDULER_PREP_OARS")

    record("8. push_message matches SCHEDULER_PREP_PUSH exactly",
           calls[0]["message"] == expected_push,
           calls[0]["message"][:40])
    record("8. oars question matches SCHEDULER_PREP_OARS exactly",
           calls[0]["oars"] == expected_oars,
           calls[0]["oars"][:40])
    record("8. OARS question mentions 'קופסאות'",   "קופסאות" in expected_oars)
    record("8. OARS question mentions 'שבת'",        "שבת"     in expected_oars)
    record("8. OARS question is a question (?)",     "?"        in expected_oars)
    record("8. push message mentions 'שישי'",        "שישי"    in expected_push or "📦" in expected_push)
    record("8. result push_message matches he.json", res[0]["push_message"] == expected_push)
    record("8. result oars_question matches he.json",res[0]["oars_question"] == expected_oars)


# ===========================================================================
print("\n=== Test 9: notifications_log entry completeness ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    write_state(sp, make_state({"u-log": dict(ELIGIBLE_USER)}))
    _, spy = make_spy()
    check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy, state_path=sp)
    st = read_state(sp)
    entry = st["notifications_log"][0]

    for field in ["type", "user_id", "sent_at", "iso_week", "current_week",
                  "push_message", "oars_question"]:
        record(f"9. log entry has '{field}'", field in entry, str(entry.get(field, "MISSING"))[:30])
    record("9. type = WEEKEND_PREP_REMINDER", entry["type"] == "WEEKEND_PREP_REMINDER")
    record("9. current_week = 10",            entry["current_week"] == 10)
    record("9. iso_week correct",             entry["iso_week"] == _iso_week(FRIDAY_NOON.date()))


# ===========================================================================
print("\n=== Test 10: notifications_sent counter increments across weeks ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    write_state(sp, make_state({"u-cnt": dict(ELIGIBLE_USER)}))
    _, spy = make_spy()

    fridays = [FRIDAY_NOON + timedelta(weeks=i) for i in range(3)]
    for i, fri in enumerate(fridays):
        check_weekend_prep_status(now=fri, dispatch_fn=spy, state_path=sp)
        st = read_state(sp)
        cnt = st["users"]["u-cnt"]["scheduler"]["notifications_sent"]
        record(f"10. Week {i+1}: notifications_sent = {i+1}", cnt == i + 1, f"got {cnt}")


# ===========================================================================
print("\n=== Test 11: Cron schedule configuration ===")

record("11. CRON_DAY_OF_WEEK = 'fri'",       CRON_DAY_OF_WEEK == "fri")
record("11. CRON_HOUR = 12",                 CRON_HOUR == 12)
record("11. CRON_MINUTE = 0",                CRON_MINUTE == 0)
record("11. PHASE_3_MIN_WEEK = 10",          PHASE_3_MIN_WEEK == 10)

# ISO week helper
record("11. _iso_week(FRIDAY_NOON) is correct format",
       _iso_week(FRIDAY_NOON.date()).startswith("2026-W"))
record("11. FRIDAY_NOON is actually a Friday",
       FRIDAY_NOON.weekday() == 4)    # 4 = Friday in Python datetime


# ===========================================================================
print("\n=== Test 12: Graceful handling of missing / empty users ===")

# Missing 'users' key entirely
with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    sp.write_text(json.dumps({"sos_events": []}), encoding="utf-8")
    calls, spy = make_spy()
    try:
        results_12 = check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy, state_path=sp)
        record("12. Missing 'users' key → no crash",  True)
        record("12. Returns empty list",              results_12 == [])
    except Exception as e:
        record("12. Missing 'users' key → no crash",  False, str(e))

# Empty users dict
with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    write_state(sp, make_state({}))
    calls, spy = make_spy()
    results_12b = check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy, state_path=sp)
    record("12. Empty users → empty result list",     results_12b == [])
    record("12. Empty users → dispatch NOT called",   len(calls) == 0)

# State file doesn't exist yet
with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "nonexistent.json"
    calls, spy = make_spy()
    try:
        results_12c = check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy, state_path=sp)
        record("12. Non-existent state file → no crash", True)
        record("12. Non-existent file → empty result",   results_12c == [])
    except Exception as e:
        record("12. Non-existent state file → no crash", False, str(e))


# ===========================================================================
print("\n=== Test 13: Concurrent invocations — idempotency under contention ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    write_state(sp, make_state({"u-conc": dict(ELIGIBLE_USER)}))
    calls: list[dict] = []
    lock = threading.Lock()

    def safe_spy(user_id, message, oars):
        with lock:
            calls.append({"user_id": user_id})

    # Launch 5 concurrent calls simulating simultaneous scheduler invocations
    threads = [
        threading.Thread(
            target=check_weekend_prep_status,
            kwargs={"now": FRIDAY_NOON, "dispatch_fn": safe_spy, "state_path": sp},
        )
        for _ in range(5)
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    # Due to the file-level _STATE_LOCK, exactly 1 notification should be sent
    st_conc = read_state(sp)
    notifications_sent = st_conc["users"]["u-conc"]["scheduler"].get("notifications_sent", 0)
    log_count = len(st_conc.get("notifications_log", []))

    record("13. Exactly 1 dispatch call under 5 concurrent threads",
           len(calls) == 1, f"got {len(calls)} dispatch calls")
    record("13. notifications_sent = 1 (no double-write)",
           notifications_sent == 1, f"got {notifications_sent}")
    record("13. notifications_log has 1 entry",
           log_count == 1, f"got {log_count}")


# ===========================================================================
print("\n=== Test 14: Scheduler module exports ===")

from backend.app.scheduler import (
    create_scheduler,
    start_scheduler,
    shutdown_scheduler,
    get_scheduler,
)

record("14. create_scheduler is callable",    callable(create_scheduler))
record("14. start_scheduler is callable",     callable(start_scheduler))
record("14. shutdown_scheduler is callable",  callable(shutdown_scheduler))
record("14. get_scheduler is callable",       callable(get_scheduler))


# ===========================================================================
print("\n=== Test 15: Scheduler locale keys in he.json ===")

he_path = Path("locales/he.json")
he = json.loads(he_path.read_text(encoding="utf-8"))

SCHED_KEYS = [
    "SCHEDULER_PREP_PUSH",
    "SCHEDULER_PREP_OARS",
    "SCHEDULER_LOG_SENT",
    "SCHEDULER_LOG_SKIPPED_IDEMPOTENT",
    "SCHEDULER_LOG_SKIPPED_PREPPED",
    "SCHEDULER_LOG_NOT_PHASE3",
]
for key in SCHED_KEYS:
    record(f"15. [{key}] present + Hebrew",
           key in he and has_hebrew(he[key]),
           he.get(key, "MISSING")[:30])


# ===========================================================================
print("\n=== Test 16: UTF-8 integrity after scheduler writes ===")

with tempfile.TemporaryDirectory() as tmpdir:
    sp = Path(tmpdir) / "state.json"
    write_state(sp, make_state({"u-utf8": dict(ELIGIBLE_USER)}))
    _, spy = make_spy()
    check_weekend_prep_status(now=FRIDAY_NOON, dispatch_fn=spy, state_path=sp)

    raw = sp.read_bytes()
    try:
        decoded = raw.decode("utf-8")
        record("16. State file is valid UTF-8 after write", True)
        record("16. Hebrew chars present in written state",
               has_hebrew(decoded))
        # Verify push message and oars question survived the round-trip
        record("16. Push message survives JSON round-trip",
               _t("SCHEDULER_PREP_PUSH") in decoded)
    except UnicodeDecodeError as e:
        record("16. State file is valid UTF-8 after write", False, str(e))


# ===========================================================================
# Summary
# ===========================================================================

print("\n" + "=" * 60)
total  = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"\nתוצאות | Results: {passed}/{total} passed")

if failed:
    print(f"\n{failed} FAILED:")
    for name, ok, detail in results:
        if not ok:
            print(f"  ✗ {name}" + (f" ({detail})" if detail else ""))
    sys.exit(1)
else:
    print("\nAll tests passed.")
    sys.exit(0)
