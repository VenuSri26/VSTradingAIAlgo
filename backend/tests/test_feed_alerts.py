from app.feed_alerts import FeedAlertHistory, evaluate_feed_alerts


def base_state():
    return {
        "authenticated": True,
        "connected": True,
        "last_market_timestamp": "2026-08-06T04:30:00+00:00",
        "last_success_at": "2026-08-06T04:30:00+00:00",
        "token_checked_at": "2026-08-06T04:29:00+00:00",
        "consecutive_failures": 0,
        "websocket_requested": False,
        "websocket_active": False,
        "expiry": "2026-08-13",
        "instruments_synced": 100,
    }


def test_ready_feed_has_no_alerts():
    result = evaluate_feed_alerts(base_state(), now="2026-08-06T04:30:05+00:00", stale_after_sec=15)
    assert result["status"] == "READY"
    assert result["alerts"] == []


def test_stale_and_auth_failure_blocks():
    state = base_state()
    state["authenticated"] = False
    result = evaluate_feed_alerts(state, now="2026-08-06T04:31:00+00:00", stale_after_sec=15)
    codes = {x["code"] for x in result["alerts"]}
    assert result["status"] == "BLOCKED"
    assert {"BROKER_AUTH_FAILED", "STALE_MARKET_DATA"}.issubset(codes)


def test_history_deduplicates_identical_state(tmp_path):
    store = FeedAlertHistory(str(tmp_path / "alerts.jsonl"))
    payload = {"evaluated_at":"a", "status":"READY", "critical_count":0, "warning_count":0, "alerts":[]}
    store.record(payload)
    store.record({**payload, "evaluated_at":"b"})
    assert len(store.list()) == 1
