# -*- coding: utf-8 -*-
"""
content_service.py — 13-week curriculum loader + Unsplash image resolution.

The curated curriculum lives in backend/content/program_content.json (one entry
per program day, 1-91). This module:
  • loads and indexes it by absolute program day,
  • resolves each entry's imageQuery to a real image URL via the Unsplash API
    (cached in the DB so each query is fetched only once),
  • exposes get_day_content() for the /content/today endpoint and for injecting
    the day's lesson into the AI mentor prompt.

UNSPLASH_ACCESS_KEY is read from the environment (set in Render, never hardcoded).
When it is absent, content is still served — just without an image URL.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from backend.app import db_service

logger = logging.getLogger(__name__)

# parents[1] = backend/  (backend/app/content_service.py -> backend/app -> backend)
_CONTENT_PATH = Path(__file__).resolve().parents[1] / "content" / "program_content.json"

_UNSPLASH_SEARCH = "https://api.unsplash.com/search/photos"


# ---------------------------------------------------------------------------
# Curriculum loading (cached in memory)
# ---------------------------------------------------------------------------

_DAYS_BY_NUMBER: dict[int, dict] | None = None


def _parse_day_number(entry_id: str) -> int | None:
    """Extract the absolute program day from an id like 'W8_D50' -> 50."""
    try:
        return int(entry_id.split("_D")[1])
    except (IndexError, ValueError):
        return None


def _load_curriculum() -> dict[int, dict]:
    """Load and index the curriculum by absolute day number (memoized)."""
    global _DAYS_BY_NUMBER
    if _DAYS_BY_NUMBER is not None:
        return _DAYS_BY_NUMBER

    with open(_CONTENT_PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    indexed: dict[int, dict] = {}
    for entry in data.get("days", []):
        day_num = _parse_day_number(entry.get("id", ""))
        if day_num is not None:
            indexed[day_num] = entry
    _DAYS_BY_NUMBER = indexed
    logger.info("content_service: loaded %d curriculum days", len(indexed))
    return indexed


def get_day_entry(day_number: int) -> Optional[dict]:
    """Return the raw curriculum entry for an absolute program day (1-91)."""
    curriculum = _load_curriculum()
    clamped = max(1, min(91, day_number))
    return curriculum.get(clamped)


# ---------------------------------------------------------------------------
# Unsplash image resolution (DB-cached)
# ---------------------------------------------------------------------------


def _fetch_unsplash(query: str) -> Optional[dict]:
    """
    Call the Unsplash search API for one landscape image.
    Returns {image_url, photographer, photographer_url} or None on any failure
    (missing key, network error, no results) — never raises.
    """
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if not access_key:
        return None

    params = urllib.parse.urlencode({
        "query": query,
        "per_page": 1,
        "orientation": "landscape",
        "content_filter": "high",
        "client_id": access_key,
    })
    url = f"{_UNSPLASH_SEARCH}?{params}"

    try:
        req = urllib.request.Request(url, headers={"Accept-Version": "v1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning("Unsplash fetch failed for %r: %s", query, exc)
        return None

    results = payload.get("results") or []
    if not results:
        return None

    first = results[0]
    return {
        "image_url":        first.get("urls", {}).get("regular"),
        "photographer":     first.get("user", {}).get("name"),
        "photographer_url": first.get("user", {}).get("links", {}).get("html"),
    }


def resolve_image(db: Session, query: str) -> Optional[dict]:
    """
    Return {image_url, photographer, photographer_url} for a query, using the
    DB cache first and falling back to a live Unsplash fetch (then caching it).
    Returns None when no image can be resolved (e.g. no API key configured).
    """
    if not query:
        return None

    cached = db_service.get_cached_image(db, query)
    if cached is not None:
        return {
            "image_url":        cached.image_url,
            "photographer":     cached.photographer,
            "photographer_url": cached.photographer_url,
        }

    fetched = _fetch_unsplash(query)
    if not fetched or not fetched.get("image_url"):
        return None

    try:
        db_service.set_cached_image(
            db=db,
            query=query,
            image_url=fetched["image_url"],
            photographer=fetched.get("photographer"),
            photographer_url=fetched.get("photographer_url"),
            fetched_at_utc=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to cache image for %r: %s", query, exc)

    return fetched


# ---------------------------------------------------------------------------
# Public: assembled day content (lesson + resolved image)
# ---------------------------------------------------------------------------


def get_day_content(db: Session, day_number: int) -> Optional[dict]:
    """
    Return the full day payload for the app: the curriculum entry plus a
    resolved image (image_url + credit). Returns None if the day is out of range.
    """
    entry = get_day_entry(day_number)
    if entry is None:
        return None

    image = resolve_image(db, entry.get("imageQuery", ""))

    return {
        "id":              entry.get("id"),
        "day_number":      max(1, min(91, day_number)),
        "phase":           entry.get("phase"),
        "theme":           entry.get("theme"),
        "videoTitle":      entry.get("videoTitle"),
        "videoUrl":        entry.get("videoUrl") or None,
        "keyTakeaway":     entry.get("keyTakeaway"),
        "educationalText": entry.get("educationalText"),
        "dailyMission":    entry.get("dailyMission"),
        "image":           image,  # {image_url, photographer, photographer_url} or None
    }
