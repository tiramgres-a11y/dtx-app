# -*- coding: utf-8 -*-
"""
LLM Router — AI Mentor Coach powered by Claude (Anthropic).

Public API
----------
  generate_mentor_response(user_state: dict, week: int) -> dict
      Core function.  Returns a plain Python dict:
        {
          "mentor_text":  str,
          "action_url":   str | None,
          "action_label": str | None
        }

  get_mentor_response(physiological_data: dict, dtx_week: int, ...) -> MentorResponse
      Thin Pydantic wrapper used by the FastAPI endpoint.

Design notes
------------
  • Model     : claude-sonnet-4-6
  • Output    : pure JSON forced via system-prompt instructions — no markdown,
                no prose, no wrapper objects.  Parsed with json.loads().
  • Fallback  : any APIError / timeout / parse error returns FALLBACK_RESPONSE
                so the endpoint always returns something useful.
  • API key   : loaded from backend/.env via python-dotenv — NEVER hardcoded.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Load .env (backend/.env takes priority; CWD .env as fallback)
# ---------------------------------------------------------------------------

_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=_env_path, override=False)
load_dotenv(override=False)  # fallback: CWD

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"

# Returned whenever the Anthropic API is unreachable or returns garbled output.
FALLBACK_RESPONSE: dict = {
    "mentor_text": (
        "אנחנו כאן איתך. כרגע לא הצלחנו להתחבר לשירות הייעוץ — "
        "נסה שוב בעוד מספר דקות. בינתיים, זכור: שתה כוס מים, "
        "עשה מתיחה קצרה, ואנחנו נחזור אליך."
    ),
    "action_url": None,
    "action_label": None,
}

# ---------------------------------------------------------------------------
# Pydantic schemas (used by the FastAPI endpoint layer)
# ---------------------------------------------------------------------------


class MentorResponse(BaseModel):
    """Structured mentor response — mirrors the plain dict returned by generate_mentor_response()."""
    mentor_text: str
    action_url: Optional[str] = None
    action_label: Optional[str] = None


class MentorChatRequest(BaseModel):
    """Request payload for POST /api/v1/mentor/chat."""
    user_id: str
    current_week: int
    sleep_hours: Optional[float] = None
    steps: Optional[int] = None
    resting_hr: Optional[int] = None
    baseline_rhr: Optional[int] = None
    free_text: Optional[str] = None


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
אתה מאמן בריאות דיגיטלי (DTx) המתמחה במניעת סוכרת סוג 2.
תפקידך: לנהל דיאלוג רציף, אמפתי ומבוסס-מדע עם המשתמש,
בהתאם לגישת OARS — שאלות פתוחות, חיזוקים, שיקופים וסיכומים.

═══ שלב א' — חדר בקרה קוגניטיבי (ניתוח פנימי סמוי) ═══
לפני כתיבת התשובה, בצע ניתוח פנימי. לעולם אל תציג את הניתוח הזה למשתמש —
אין כותרות, אין סעיפים טכניים, אין אזכור של "ניתוח" או "שלב".

1. זהה את כוונת המשתמש:
   • בקשת ידע טכני (תפריט, תרגיל, הסבר מדעי) → תן מענה מעשי ומדויק.
   • דיווח על הצלחה → חיזוק חיובי מפורש (Affirmation) שמייצר לולאת דופמין.
   • דיווח על קושי/משבר רגשי → קודם שיקוף (Reflection), בלי לתקן ובלי פתרונות
     מיידיים. מתן פתרון טכני למשבר רגשי מעורר התנגדות (Righting Reflex) — הימנע.

2. זהה את שלב השינוי לפי המודל הטרנס-תיאורטי (TTM) מתוך ההיסטוריה והנוכחי:
   • הרהור/הכנה — שאלות טכניות מרובות, חרדת ביצוע → אל תעמיס מידע. הצע צעד מודולרי אחד.
   • פעולה — דיווחי ביצוע עקביים, בקשת אתגרים → נצל מוטיבציה גבוהה, הצע העלאת דרגה.
   • תחזוקה — שאלות על גיוון ואירועים חברתיים → העבר את סמכות ההחלטה למשתמש.
   • נסיגה — "שברתי את הדיאטה", אשמה, הפסקת אימונים → בלימת הלקאה עצמית:
     נרמל את החוויה, אסור לדרוש פיצוי קלורי, הצב יעד-מיקרו ל-30 הדקות הקרובות בלבד.

3. שקלל את ההקשר הפיזיולוגי שסופק (שינה, צעדים, דופק, אירועי SOS אחרונים):
   • שינה < 6 שעות → רגישות אינסולין ירודה היום; העדף המלצת חלבון/סיבים על פחמימות.
   • אירוע SOS שלא נפתר לאחרונה → התייחס ברגישות, בלי להזכיר "אירוע" באופן טכני.

═══ שלב ב' — פלט למשתמש ═══
כללים:
1. לעולם אל תבייש, תאשים או תשפוט. שפה חמה, מכילה ומעצימה — תמיד בעברית.
2. תגובה קצרה (2–5 משפטים). סיים בשאלה פתוחה כשמתאים — לא בכל הודעה.
3. המשך את השיחה באופן טבעי — התייחס למה שנאמר קודם, אל תפתח כל תשובה מחדש.
4. עקרונות תזונה: דיאטת הפורטפוליו (חלבון צמחי ~50 גר', סיבים מסיסים ~22 גר',
   אגוזים ~45 גר', פיטוסטרולים 2 גר'). דחה דיאטות קיצון (קטו < 50 גר' פחמימה).
   לעולם אל תציע תפריט נוקשה בלי לשאול קודם על זמן, מצרכים זמינים ואלרגיות.
5. עקרונות אימון (ACSM): הדרגתיות קריטית — לעולם לא תוכנית עצימה למתחיל.
   150 דק' אירובי שבועי ("אפשר לדבר, קשה לשיר"), 2–3 אימוני כוח לא-עוקבים,
   פירוק ישיבה כל 45–60 דק'. שלב 2 (שבועות 5–9): הדגש GLUT4 אחרי ארוחות.
6. הרגלים חדשים — תמיד דרך הערמת הרגלים: "אחרי ש[פעולה קיימת], אני א[פעולה חדשה]".
6א. תכנון שבועי (Pre-planning Protocol): כשהמשתמש מבקש תכנון שבועי או רשימת קניות —
   זהו פרוטוקול הכנת סביבה. אם טרם ידוע: שאל קודם (בשאלה אחת) על זמן הכנה פנוי,
   מצרכים שכבר יש, ואלרגיות. לאחר מכן בנה רשימת קניות ממוקדת מרכיבי הפורטפוליו
   (טופו/קטניות, שיבולת שועל, אגוזים וזרעים, ירקות עתירי סיבים מסיסים) + הצעת
   יום בישול אחד. עיקרון: 30 דקות תכנון מונעות בחירות אימפולסיביות כל השבוע.
7. כאשר רלוונטי, כלול קישור אחד מהרשימה (ורק מהרשימה):
   - ארוחת בוקר עשירה בחלבון: https://dtx.app/recipes/high-protein-breakfast
   - ארוחת ערב לסוכר יציב: https://dtx.app/recipes/stable-blood-sugar-dinner
   - חטיף אגוזים ואוכמניות: https://dtx.app/recipes/nuts-blueberries-snack
   - סלט חלבון צמחי: https://dtx.app/recipes/plant-protein-salad
   - שייק ירוק לאחר אימון: https://dtx.app/recipes/post-workout-green-shake
   - תרגיל 5 דקות אחרי ארוחה: https://dtx.app/exercises/5min-post-meal

פורמט תשובה חובה — JSON בלבד:
החזר אך ורק JSON תקני. אין להוסיף טקסט, markdown, הסברים, או רווחים לפני/אחרי ה-JSON.
המבנה המדויק:
{
  "mentor_text": "...",
  "action_url": "..." | null,
  "action_label": "..." | null
}
"""

# ---------------------------------------------------------------------------
# Phase helper
# ---------------------------------------------------------------------------


def _week_to_phase(week: int) -> str:
    if 1 <= week <= 4:
        return "שלב 1 — איפוס (שבועות 1–4)"
    if 5 <= week <= 9:
        return "שלב 2 — עומס מטבולי / GLUT4 (שבועות 5–9)"
    if 10 <= week <= 13:
        return "שלב 3 — תחזוקה ומודולריות (שבועות 10–13)"
    return f"שבוע {week}"


# ---------------------------------------------------------------------------
# Core function — returns a plain dict
# ---------------------------------------------------------------------------


def generate_mentor_response(
    user_state: dict,
    week: int,
    history: Optional[list[dict]] = None,
    sos_context: Optional[list[dict]] = None,
) -> dict:
    """
    Generate a personalised, OARS-compliant Hebrew mentor message.

    Args:
        user_state: dict with any of:
            sleep_hours  (float)
            steps        (int)
            resting_hr   (int)
            baseline_rhr (int)
            free_text    (str)  — optional user-typed note
        week: current DTx programme week (1–13).
        history: prior conversation turns, chronological — each
            {"role": "user"|"coach", "content": str}. Injected as multi-turn
            messages so the model continues the dialogue naturally.
        sos_context: recent SOS events — each
            {"timestamp_utc": str, "resolution_status": str|None}.
            Surfaced to the cognitive control room as physiological context.

    Returns:
        dict with keys: mentor_text (str), action_url (str|None), action_label (str|None).
        On any error (API failure, timeout, invalid JSON) returns FALLBACK_RESPONSE.

    Raises:
        ValueError: if ANTHROPIC_API_KEY is missing or is a placeholder.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("your_") or api_key.startswith("sk-ant-test"):
        raise ValueError(
            "ANTHROPIC_API_KEY is not configured. "
            "Copy backend/.env.example → backend/.env and add your real key."
        )

    # --- build user message ---------------------------------------------------
    phase = _week_to_phase(week)
    lines = [f"שבוע תוכנית: {week} ({phase})"]

    sleep = user_state.get("sleep_hours")
    if sleep is not None:
        lines.append(f"שינה הלילה: {sleep} שעות")

    steps = user_state.get("steps")
    if steps is not None:
        lines.append(f"צעדים היום: {steps:,}")

    rhr = user_state.get("resting_hr")
    if rhr is not None:
        lines.append(f"דופק במנוחה: {rhr} פעימות/דקה")

    baseline = user_state.get("baseline_rhr")
    if baseline is not None:
        lines.append(f"דופק בסיס אישי: {baseline} פעימות/דקה")

    # Recent SOS events — context for the cognitive control room
    if sos_context:
        sos_lines = []
        for ev in sos_context:
            status = ev.get("resolution_status")
            status_he = {
                "SUCCESS": "נפתר בהצלחה (עמד בפיתוי)",
                "LAPSE":   "הסתיים במעידה",
            }.get(status, "טרם נפתר")
            sos_lines.append(f"  - {ev.get('timestamp_utc', '?')}: {status_he}")
        lines.append("\nאירועי SOS (דחף/השתוקקות) אחרונים:\n" + "\n".join(sos_lines))

    free_text = user_state.get("free_text")
    if free_text:
        lines.append(f"\nהמשתמש כתב: {free_text}")

    lines.append(
        "\nהחזר אך ורק JSON תקני לפי הפורמט שצוין בהוראות המערכת. "
        "ללא markdown, ללא טקסט נוסף."
    )
    user_message = "\n".join(lines)

    # --- build multi-turn message list ----------------------------------------
    # Prior turns are injected as real conversation turns so the model continues
    # the dialogue naturally instead of restarting on every request.
    messages: list[dict] = []
    for turn in history or []:
        role = "assistant" if turn.get("role") == "coach" else "user"
        content = turn.get("content", "")
        if not content:
            continue
        # Assistant turns must mirror the JSON output format the model is
        # instructed to produce — otherwise it may mimic plain-text replies.
        if role == "assistant":
            content = json.dumps({"mentor_text": content}, ensure_ascii=False)
        # Collapse consecutive same-role turns (Anthropic requires alternation)
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n" + content
        else:
            messages.append({"role": role, "content": content})
    # The current request must be the final user turn
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n\n" + user_message
    else:
        messages.append({"role": "user", "content": user_message})

    # --- call Anthropic API ---------------------------------------------------
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        raw_text = response.content[0].text.strip()

        # Strip accidental markdown fences if the model adds them despite instructions
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        parsed = json.loads(raw_text)

        # Validate required key
        if "mentor_text" not in parsed:
            raise ValueError(f"JSON missing 'mentor_text' key: {raw_text!r}")

        result = {
            "mentor_text":  str(parsed["mentor_text"]),
            "action_url":   parsed.get("action_url") or None,
            "action_label": parsed.get("action_label") or None,
        }
        logger.info(
            "generate_mentor_response: week=%d phase=%s action_url=%s",
            week, phase, result["action_url"],
        )
        return result

    except anthropic.APITimeoutError as exc:
        logger.warning("LLM Router: API timeout — returning fallback. %s", exc)
        return FALLBACK_RESPONSE.copy()

    except anthropic.APIConnectionError as exc:
        logger.warning("LLM Router: connection error — returning fallback. %s", exc)
        return FALLBACK_RESPONSE.copy()

    except anthropic.RateLimitError as exc:
        logger.warning("LLM Router: rate limit hit — returning fallback. %s", exc)
        return FALLBACK_RESPONSE.copy()

    except anthropic.APIStatusError as exc:
        logger.error("LLM Router: API status %s — returning fallback. %s", exc.status_code, exc)
        return FALLBACK_RESPONSE.copy()

    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.error("LLM Router: JSON parse error — returning fallback. %s", exc)
        return FALLBACK_RESPONSE.copy()


# ---------------------------------------------------------------------------
# Pydantic wrapper — used by the FastAPI endpoint
# ---------------------------------------------------------------------------


def get_mentor_response(
    physiological_data: dict,
    dtx_week: int,
    free_text: Optional[str] = None,
    history: Optional[list[dict]] = None,
    sos_context: Optional[list[dict]] = None,
) -> MentorResponse:
    """
    FastAPI-friendly wrapper around generate_mentor_response().
    Merges free_text into physiological_data and returns a MentorResponse model.
    Propagates ValueError (missing API key) for the endpoint to convert to HTTP 503.
    """
    state = dict(physiological_data)
    if free_text:
        state["free_text"] = free_text

    result = generate_mentor_response(
        user_state=state,
        week=dtx_week,
        history=history,
        sos_context=sos_context,
    )
    return MentorResponse(**result)
