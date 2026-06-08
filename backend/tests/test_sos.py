# -*- coding: utf-8 -*-
"""
test_sos.py — Tests for the SOS Craving Toolkit endpoints.

Covers:
  * POST /api/v1/sos/trigger — event logging + protocol response
  * POST /api/v1/sos/resolve — SUCCESS and LAPSE resolution paths
  * Idempotency: resolving an unknown timestamp → 404
  * LAPSE resolution queues a morning payload in the DB
"""

from __future__ import annotations

from backend.app import db_service


# ---------------------------------------------------------------------------
# /trigger
# ---------------------------------------------------------------------------


def test_sos_trigger_returns_protocol(client):
    r = client.post("/api/v1/sos/trigger", json={
        "user_id": "sos-user-1",
        "week_context": 11,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["event_logged"] is True
    assert len(data["protocol_steps"]) == 3
    assert "empathy_message_he" in data
    assert data["week_context"] == 11


def test_sos_trigger_logs_to_db(client, db):
    from sqlalchemy import select
    from backend.models import SOSEvent

    r = client.post("/api/v1/sos/trigger", json={
        "user_id": "sos-db-check",
        "week_context": 11,
    })
    assert r.status_code == 200
    ts = r.json()["timestamp_utc"]

    events = db.scalars(
        select(SOSEvent).where(SOSEvent.user_id == "sos-db-check")
    ).all()
    assert len(events) == 1
    assert events[0].timestamp_utc == ts
    assert events[0].resolution_status is None


def test_sos_trigger_week_context_validation(client):
    """week_context must be 1-13."""
    r = client.post("/api/v1/sos/trigger", json={
        "user_id": "sos-user",
        "week_context": 99,
    })
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /resolve — SUCCESS path
# ---------------------------------------------------------------------------


def test_sos_resolve_success(client):
    # First trigger
    trigger = client.post("/api/v1/sos/trigger", json={
        "user_id": "sos-resolve-user",
        "week_context": 11,
    })
    ts = trigger.json()["timestamp_utc"]

    r = client.post("/api/v1/sos/resolve", json={
        "user_id": "sos-resolve-user",
        "event_timestamp_utc": ts,
        "status": "SUCCESS",
        "week_context": 12,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "SUCCESS"
    assert data["morning_queue"] is None
    assert "acknowledgement_he" in data


def test_sos_resolve_success_updates_db(client, db):
    from sqlalchemy import select
    from backend.models import SOSEvent

    trigger = client.post("/api/v1/sos/trigger", json={
        "user_id": "sos-success-db",
        "week_context": 11,
    })
    ts = trigger.json()["timestamp_utc"]

    client.post("/api/v1/sos/resolve", json={
        "user_id": "sos-success-db",
        "event_timestamp_utc": ts,
        "status": "SUCCESS",
        "week_context": 12,
    })

    event = db.scalars(
        select(SOSEvent).where(SOSEvent.user_id == "sos-success-db")
    ).first()
    assert event.resolution_status == "SUCCESS"
    assert event.resolved_at_utc is not None


# ---------------------------------------------------------------------------
# /resolve — LAPSE path
# ---------------------------------------------------------------------------


def test_sos_resolve_lapse_queues_morning_payload(client, db):
    from sqlalchemy import select
    from backend.models import MorningQueueEntry

    trigger = client.post("/api/v1/sos/trigger", json={
        "user_id": "sos-lapse-user",
        "week_context": 11,
    })
    ts = trigger.json()["timestamp_utc"]

    r = client.post("/api/v1/sos/resolve", json={
        "user_id": "sos-lapse-user",
        "event_timestamp_utc": ts,
        "status": "LAPSE",
        "week_context": 12,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "LAPSE"
    assert data["morning_queue"] is not None
    assert "oars_affirmation_he" in data["morning_queue"]

    # Verify DB row
    entry = db.scalars(
        select(MorningQueueEntry).where(MorningQueueEntry.user_id == "sos-lapse-user")
    ).first()
    assert entry is not None
    assert entry.oars_affirmation_he != ""


# ---------------------------------------------------------------------------
# Unknown timestamp → 404
# ---------------------------------------------------------------------------


def test_sos_resolve_unknown_timestamp_404(client):
    r = client.post("/api/v1/sos/resolve", json={
        "user_id": "no-such-user",
        "event_timestamp_utc": "1970-01-01T00:00:00+00:00",
        "status": "SUCCESS",
        "week_context": 12,
    })
    assert r.status_code == 404
