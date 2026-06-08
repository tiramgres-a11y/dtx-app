#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone integration test for the LLM Router.

Usage
-----
  1. Create the .env file (see printed instructions below).
  2. Run from the project root:
        python backend/test_llm_router.py

This script does NOT use pytest — it runs as a plain Python script so you
can see the live response from Claude without any test harness overhead.

What it tests
-------------
  Simulated user: sleep-deprived (4.5 h), Week 4 (Phase 1 — Reset).
  Expected: Hebrew OARS reflection, menu-adjustment advice, optional recipe link.
"""

from __future__ import annotations

import json
import os
import sys

# ── Force UTF-8 output on Windows (Hebrew characters require it) ──────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Pretty banner ─────────────────────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║           DTx LLM Router — Integration Test Script              ║
║           Model: claude-sonnet-4-6                               ║
╚══════════════════════════════════════════════════════════════════╝
"""

SETUP_INSTRUCTIONS = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  HOW TO SET UP YOUR .env FILE BEFORE RUNNING THIS TEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Step 1 — Get your Anthropic API key:
           https://console.anthropic.com/account/keys

  Step 2 — Create the .env file (run ONE of the following commands
           from the project root — C:\\Projects\\dtx):

           Windows (PowerShell):
             Copy-Item backend\\.env.example backend\\.env
             notepad backend\\.env

           macOS / Linux:
             cp backend/.env.example backend/.env
             nano backend/.env  (or open with any editor)

  Step 3 — Replace the placeholder value:
             ANTHROPIC_API_KEY=your_anthropic_api_key_here
           with your actual key:
             ANTHROPIC_API_KEY=sk-ant-api03-...

  Step 4 — Save the file, then re-run this script:
             python backend/test_llm_router.py

  ⚠️  NEVER commit backend/.env to version control.
      The file is listed in .gitignore for your protection.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ── Ensure project root is on sys.path ────────────────────────────────────────

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── Load .env before importing llm_router (it also loads, but being explicit) ─

from dotenv import load_dotenv  # noqa: E402

_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=_env_file, override=False)

# ── Import after path setup ───────────────────────────────────────────────────

from backend.llm_router import generate_mentor_response, FALLBACK_RESPONSE  # noqa: E402


# ── Test scenario ─────────────────────────────────────────────────────────────

TEST_USER_STATE: dict = {
    "sleep_hours":   4.5,    # severely sleep-deprived
    "steps":         3_200,  # low activity
    "resting_hr":    74,     # slightly elevated
    "baseline_rhr":  62,     # personal baseline (stored from onboarding)
}

TEST_WEEK: int = 4  # Phase 1 — Reset (last week before Phase 2)


def _validate_response(data: dict) -> list[str]:
    """Return a list of validation errors (empty = all good)."""
    errors: list[str] = []

    if not isinstance(data, dict):
        return [f"Response is not a dict: {type(data)}"]

    # mentor_text — required, non-empty string
    if "mentor_text" not in data:
        errors.append("❌  Missing key: 'mentor_text'")
    elif not isinstance(data["mentor_text"], str) or len(data["mentor_text"].strip()) == 0:
        errors.append("❌  'mentor_text' must be a non-empty string")

    # action_url — must be str or None
    if "action_url" not in data:
        errors.append("❌  Missing key: 'action_url'")
    elif data["action_url"] is not None and not isinstance(data["action_url"], str):
        errors.append(f"❌  'action_url' must be str or null, got {type(data['action_url'])}")

    # action_label — must be str or None
    if "action_label" not in data:
        errors.append("❌  Missing key: 'action_label'")
    elif data["action_label"] is not None and not isinstance(data["action_label"], str):
        errors.append(f"❌  'action_label' must be str or null, got {type(data['action_label'])}")

    return errors


def main() -> None:
    print(BANNER)
    print(SETUP_INSTRUCTIONS)

    # ── Check API key ─────────────────────────────────────────────────────────
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("your_") or api_key.startswith("sk-ant-test"):
        print("⛔  ANTHROPIC_API_KEY is not set or is still a placeholder.")
        print("    Follow the setup instructions above, then re-run this script.\n")
        sys.exit(1)

    print(f"✅  API key detected: {api_key[:12]}{'*' * max(0, len(api_key) - 20)}{api_key[-4:]}\n")

    # ── Print test scenario ───────────────────────────────────────────────────
    print("─" * 64)
    print("  TEST SCENARIO")
    print("─" * 64)
    print(f"  Week       : {TEST_WEEK}  (Phase 1 — Reset)")
    print(f"  Sleep      : {TEST_USER_STATE['sleep_hours']} hours  ← severely sleep-deprived")
    print(f"  Steps      : {TEST_USER_STATE['steps']:,}")
    print(f"  Resting HR : {TEST_USER_STATE['resting_hr']} BPM  (baseline: {TEST_USER_STATE['baseline_rhr']} BPM)")
    print()

    # ── Call the LLM Router ───────────────────────────────────────────────────
    print("  Calling Claude API…")
    try:
        result = generate_mentor_response(user_state=TEST_USER_STATE, week=TEST_WEEK)
    except ValueError as exc:
        print(f"\n⛔  Configuration error: {exc}\n")
        sys.exit(1)

    # ── Print raw parsed JSON ─────────────────────────────────────────────────
    print("\n─" * 64)
    print("  PARSED JSON RESPONSE")
    print("─" * 64)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # ── Validate schema ───────────────────────────────────────────────────────
    errors = _validate_response(result)

    print("\n─" * 64)
    print("  VALIDATION")
    print("─" * 64)

    is_fallback = result.get("mentor_text") == FALLBACK_RESPONSE["mentor_text"]
    if is_fallback:
        print("⚠️   Fallback response was returned (API unreachable or parse error).")
        print("    Check your internet connection and API key, then try again.")

    if errors:
        for err in errors:
            print(f"  {err}")
        print(f"\n❌  {len(errors)} validation error(s) found.\n")
        sys.exit(1)
    else:
        print("  ✅  mentor_text  — present, non-empty string")
        print(f"  {'✅' if result['action_url'] else '➖'}  action_url   — {result['action_url'] or 'null (no link this time)'}")
        print(f"  {'✅' if result['action_label'] else '➖'}  action_label — {result['action_label'] or 'null'}")
        print()
        print("  ✅  All schema checks passed.\n")

    # ── Human-readable mentor text ────────────────────────────────────────────
    print("─" * 64)
    print("  MENTOR TEXT (Hebrew)")
    print("─" * 64)
    print()
    print(f"  {result['mentor_text']}")
    print()
    if result.get("action_url"):
        print(f"  🔗  {result['action_label']}")
        print(f"      {result['action_url']}")
        print()

    print("=" * 64)
    print("  LLM Router integration test PASSED ✅")
    print("=" * 64)
    print()


if __name__ == "__main__":
    main()
