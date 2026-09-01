from app.feed_watchdog import evaluate_feed_safety
from app.market_clock import market_clock, normalize_exchange_timestamp


def healthy_state():
    return {
        "connected": True,
        "authenticated": True,
        "last_market_timestamp": "2026-08-05T10:00:00+05:30",
        "last_success_at": "2026-08-05T10:00:00+05:30",
        "token_checked_at": "2026-08-05T09:55:00+05:30",
        "consecutive_failures": 0,
        "websocket_requested": True,
        "websocket_active": False,
        "instruments_synced": 100,
        "expiry": "2026-08-06",
        "mode": "SAFE_REST_POLLING",
    }


def test_market_clock_open_and_holiday():
    assert market_clock("2026-08-05T10:00:00+05:30").market_open is True
    closed = market_clock("2026-08-05T10:00:00+05:30", holidays="2026-08-05")
    assert closed.market_open is False
    assert closed.reason == "MARKET_HOLIDAY"


def test_timestamp_normalization_assumes_ist_for_naive_exchange_time():
    assert normalize_exchange_timestamp("2026-08-05T10:00:00").endswith("+00:00")
    assert normalize_exchange_timestamp("2026-08-05T10:00:00") == "2026-08-05T04:30:00+00:00"


def test_feed_ready_with_rest_fallback_warning():
    result = evaluate_feed_safety(
        healthy_state(), now="2026-08-05T10:00:05+05:30", stale_after_sec=15,
    )
    assert result["status"] == "READY"
    assert result["recommended_action"] == "ALLOW_DECISION_SUPPORT"
    assert "WebSocket requested but REST fallback is active" in result["warnings"]


def test_feed_blocks_stale_or_closed_market():
    stale = evaluate_feed_safety(
        healthy_state(), now="2026-08-05T10:01:00+05:30", stale_after_sec=15,
    )
    assert stale["status"] == "BLOCKED"
    assert stale["recommended_action"] == "NO_TRADE"
    closed = evaluate_feed_safety(
        healthy_state(), now="2026-08-08T10:00:05+05:30", stale_after_sec=15,
    )
    assert closed["status"] == "BLOCKED"
    assert any("Market session" in x for x in closed["blockers"])
