"""
Tests for the logic extracted out of the POST /api/live-paper/prepare route
handler (app/live_paper_bridge_routes.py) into pure, FastAPI-free functions
in app/live_paper_bridge.py. The route itself still needs a running FastAPI
app to test end-to-end; this covers the actual business logic that used to
live inline in the handler with zero coverage:
  - confirmation-phrase validation
  - rejecting a non-ready preview (PaperSetupNotReady, carrying the result)
  - creating a trade setup from a ready preview
  - designed-in dedup: re-preparing the same candidate returns the existing
    setup instead of creating a duplicate
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app import store
from app.live_paper_bridge import (
    PaperSetupNotReady,
    REQUIRED_CONFIRMATION_TEXT,
    build_paper_setup_candidate,
    prepare_paper_setup_from_preview,
    validate_confirmation_text,
)


def _snapshot():
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "spot": 25210,
        "expiry": "2026-08-06",
        "chain": {
            "CE": [
                {"strike": 25200, "oi": 500, "ltp": 100},
                {"strike": 25250, "oi": 900, "ltp": 72},
            ],
            "PE": [
                {"strike": 25200, "oi": 1000, "ltp": 92},
                {"strike": 25150, "oi": 700, "ltp": 65},
            ],
        },
    }


def _ready_preview():
    result = build_paper_setup_candidate(_snapshot(), {"trend": "BULLISH_STRENGTHENING"})
    assert result["status"] == "READY_FOR_HUMAN_REVIEW"
    return result


def _blocked_preview():
    result = build_paper_setup_candidate(_snapshot(), {"trend": "NEUTRAL"})
    assert result["status"] == "BLOCKED"
    return result


def test_validate_confirmation_text_accepts_exact_phrase():
    validate_confirmation_text(REQUIRED_CONFIRMATION_TEXT)  # must not raise


def test_validate_confirmation_text_rejects_anything_else():
    with pytest.raises(ValueError, match="Type PREPARE_PAPER_SETUP to create a draft"):
        validate_confirmation_text("prepare_paper_setup")  # wrong case
    with pytest.raises(ValueError):
        validate_confirmation_text("")


def test_prepare_rejects_a_blocked_preview_and_carries_the_result():
    blocked = _blocked_preview()
    with pytest.raises(PaperSetupNotReady) as exc_info:
        prepare_paper_setup_from_preview(blocked)
    assert exc_info.value.result is blocked
    assert exc_info.value.result["status"] == "BLOCKED"


def test_prepare_creates_a_paper_only_trade_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "prepare.db"))
    result = _ready_preview()

    response = prepare_paper_setup_from_preview(result)

    assert response["created"] is True
    setup = response["setup"]
    assert setup is not None
    assert setup["decision"] == "CE_BUY"
    assert setup["option_type"] == "CE"
    assert setup["status"] == "GENERATED"
    stored_payload = json.loads(setup["snapshot_json"])
    assert stored_payload["execution_mode"] == "PAPER_ONLY"
    assert stored_payload["source"] == "LIVE_PAPER_BRIDGE"


def test_prepare_is_idempotent_for_the_same_candidate_signature(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "dedup.db"))
    result = _ready_preview()

    first = prepare_paper_setup_from_preview(result)
    second = prepare_paper_setup_from_preview(result)

    assert first["created"] is True
    assert second["created"] is False
    assert second["reason"] == "DUPLICATE"
    assert second["setup"]["id"] == first["setup"]["id"]
