# -*- coding: utf-8 -*-
"""
Pytest unit tests for llm_router.py — AI Mentor Coach (LLM Router).

All Anthropic API calls are mocked — no real key needed.
Live integration test is skipped unless a genuine API key is present.
"""

from __future__ import annotations

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_api_response(mentor_text: str, action_url=None, action_label=None) -> MagicMock:
    """Build a fake anthropic messages.create() response object."""
    payload = json.dumps(
        {"mentor_text": mentor_text, "action_url": action_url, "action_label": action_label},
        ensure_ascii=False,
    )
    content_block = SimpleNamespace(text=payload)
    return SimpleNamespace(content=[content_block])


# ---------------------------------------------------------------------------
# Unit tests — mocked Anthropic client
# ---------------------------------------------------------------------------


class TestGenerateMentorResponse(unittest.TestCase):
    """Tests for generate_mentor_response() — the core plain-dict function."""

    def setUp(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-real-looking-key-for-tests"

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def _patch_create(self, mentor_text: str, action_url=None, action_label=None):
        fake_resp = _make_api_response(mentor_text, action_url, action_label)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake_resp
        return patch("backend.llm_router.anthropic.Anthropic", return_value=mock_client)

    # ------------------------------------------------------------------
    # Core scenario: 5 hours sleep in Phase 2 (week 6) → recipe link
    # ------------------------------------------------------------------

    def test_short_sleep_phase2_returns_recipe_link(self):
        url   = "https://dtx.app/recipes/high-protein-breakfast"
        label = "ארוחת בוקר עשירה בחלבון"
        text  = "שינה קצרה משפיעה על רגישות לאינסולין. הצלחת לקום — זה כבר הרבה!"

        with self._patch_create(text, url, label):
            from backend.llm_router import generate_mentor_response
            result = generate_mentor_response({"sleep_hours": 5.0}, week=6)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["mentor_text"], text)
        self.assertEqual(result["action_url"], url)
        self.assertTrue(result["action_url"].startswith("https://dtx.app/"))
        self.assertEqual(result["action_label"], label)

    # ------------------------------------------------------------------
    # Return type is always a plain dict
    # ------------------------------------------------------------------

    def test_returns_plain_dict_not_pydantic(self):
        with self._patch_create("מסר לדוגמה"):
            from backend.llm_router import generate_mentor_response
            result = generate_mentor_response({"sleep_hours": 7.5}, week=3)
        self.assertIsInstance(result, dict)
        self.assertNotIsInstance(result, object.__class__)  # not a Pydantic model

    def test_mentor_text_is_non_empty(self):
        with self._patch_create("כל הכבוד!"):
            from backend.llm_router import generate_mentor_response
            result = generate_mentor_response({}, week=1)
        self.assertGreater(len(result["mentor_text"]), 0)

    def test_action_fields_can_be_none(self):
        with self._patch_create("מסר", action_url=None, action_label=None):
            from backend.llm_router import generate_mentor_response
            result = generate_mentor_response({"steps": 9000}, week=2)
        self.assertIsNone(result["action_url"])
        self.assertIsNone(result["action_label"])

    # ------------------------------------------------------------------
    # API key validation
    # ------------------------------------------------------------------

    def test_missing_key_raises_value_error(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from backend.llm_router import generate_mentor_response
        with self.assertRaises(ValueError):
            generate_mentor_response({"sleep_hours": 5.0}, week=6)

    def test_placeholder_key_raises_value_error(self):
        os.environ["ANTHROPIC_API_KEY"] = "your_anthropic_api_key_here"
        from backend.llm_router import generate_mentor_response
        with self.assertRaises(ValueError):
            generate_mentor_response({"sleep_hours": 5.0}, week=6)

    # ------------------------------------------------------------------
    # Graceful fallback on API errors
    # ------------------------------------------------------------------

    def test_fallback_on_api_timeout(self):
        import anthropic as ant
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = ant.APITimeoutError(request=MagicMock())
        with patch("backend.llm_router.anthropic.Anthropic", return_value=mock_client):
            from backend.llm_router import generate_mentor_response, FALLBACK_RESPONSE
            result = generate_mentor_response({"sleep_hours": 5.0}, week=4)
        self.assertEqual(result, FALLBACK_RESPONSE)

    def test_fallback_on_connection_error(self):
        import anthropic as ant
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = ant.APIConnectionError(request=MagicMock())
        with patch("backend.llm_router.anthropic.Anthropic", return_value=mock_client):
            from backend.llm_router import generate_mentor_response, FALLBACK_RESPONSE
            result = generate_mentor_response({"sleep_hours": 5.0}, week=4)
        self.assertEqual(result, FALLBACK_RESPONSE)

    def test_fallback_on_invalid_json(self):
        """If the model ignores instructions and returns prose, fallback kicks in."""
        bad_block = SimpleNamespace(text="שלום! אני המאמן שלך...")
        mock_client = MagicMock()
        mock_client.messages.create.return_value = SimpleNamespace(content=[bad_block])
        with patch("backend.llm_router.anthropic.Anthropic", return_value=mock_client):
            from backend.llm_router import generate_mentor_response, FALLBACK_RESPONSE
            result = generate_mentor_response({"sleep_hours": 5.0}, week=4)
        self.assertEqual(result, FALLBACK_RESPONSE)

    def test_fallback_on_json_missing_mentor_text(self):
        """JSON without 'mentor_text' key → fallback."""
        bad_payload = json.dumps({"foo": "bar"})
        bad_block = SimpleNamespace(text=bad_payload)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = SimpleNamespace(content=[bad_block])
        with patch("backend.llm_router.anthropic.Anthropic", return_value=mock_client):
            from backend.llm_router import generate_mentor_response, FALLBACK_RESPONSE
            result = generate_mentor_response({"sleep_hours": 5.0}, week=4)
        self.assertEqual(result, FALLBACK_RESPONSE)

    def test_markdown_fence_stripped_before_parse(self):
        """Model wrapping JSON in ```json ... ``` should still parse correctly."""
        inner = {"mentor_text": "עדכון מעניין", "action_url": None, "action_label": None}
        fenced = "```json\n" + json.dumps(inner, ensure_ascii=False) + "\n```"
        block = SimpleNamespace(text=fenced)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = SimpleNamespace(content=[block])
        with patch("backend.llm_router.anthropic.Anthropic", return_value=mock_client):
            from backend.llm_router import generate_mentor_response
            result = generate_mentor_response({}, week=1)
        self.assertEqual(result["mentor_text"], "עדכון מעניין")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def test_week_to_phase_mapping(self):
        from backend.llm_router import _week_to_phase
        self.assertIn("1", _week_to_phase(1))
        self.assertIn("4", _week_to_phase(4))
        self.assertIn("GLUT4", _week_to_phase(5))
        self.assertIn("GLUT4", _week_to_phase(9))
        self.assertIn("10", _week_to_phase(10))
        self.assertIn("13", _week_to_phase(13))

    # ------------------------------------------------------------------
    # FastAPI endpoint — via TestClient, still mocked
    # ------------------------------------------------------------------

    def test_endpoint_returns_200_with_recipe_url(self):
        url = "https://dtx.app/recipes/nuts-blueberries-snack"
        fake_resp = _make_api_response("שינה קצרה — נסה חטיף אגוזים", url, "חטיף אגוזים")
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake_resp

        with patch("backend.llm_router.anthropic.Anthropic", return_value=mock_client):
            from fastapi.testclient import TestClient
            from backend.app.main import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/api/v1/mentor/chat",
                json={"user_id": "u1", "current_week": 6, "sleep_hours": 5.0},
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("mentor_text", body)
        self.assertIn("action_url", body)
        self.assertTrue(body["action_url"].startswith("https://dtx.app/"))

    def test_endpoint_503_when_no_api_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/mentor/chat",
            json={"user_id": "u1", "current_week": 6, "sleep_hours": 5.0},
        )
        self.assertEqual(resp.status_code, 503, resp.text)


# ---------------------------------------------------------------------------
# Live integration test — auto-skipped without a real key
# ---------------------------------------------------------------------------


def _has_real_key() -> bool:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return (
        bool(key)
        and not key.startswith("your_")
        and not key.startswith("sk-ant-test")
        and not key.startswith("sk-ant-real-looking")
    )


@pytest.mark.skipif(not _has_real_key(), reason="No real ANTHROPIC_API_KEY — skipping live test")
def test_live_sleep_deprived_week4():
    """
    Live integration: 4.5 h sleep, Week 4 (Phase 1 — Reset).
    Asserts the response is valid JSON with a non-empty mentor_text.
    """
    from backend.llm_router import generate_mentor_response

    result = generate_mentor_response(
        user_state={"sleep_hours": 4.5, "steps": 3200, "resting_hr": 74, "baseline_rhr": 62},
        week=4,
    )

    assert isinstance(result, dict)
    assert isinstance(result["mentor_text"], str)
    assert len(result["mentor_text"]) > 10
    assert "action_url" in result
    assert "action_label" in result
    if result["action_url"] is not None:
        assert result["action_url"].startswith("http")

    # Ensure it serialises cleanly
    dumped = json.loads(json.dumps(result, ensure_ascii=False))
    assert "mentor_text" in dumped


if __name__ == "__main__":
    unittest.main()
