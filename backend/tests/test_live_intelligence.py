from datetime import datetime, timedelta, timezone

from app.live_intelligence import analyse_live_market


def snapshot(age=0):
    return {
        "timestamp": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
        "spot": 25210,
        "expiry": "2026-08-06",
        "chain": {
            "CE": [
                {"strike": 25150, "oi": 100, "ltp": 95},
                {"strike": 25200, "oi": 400, "ltp": 62},
                {"strike": 25250, "oi": 900, "ltp": 38},
            ],
            "PE": [
                {"strike": 25150, "oi": 1000, "ltp": 25},
                {"strike": 25200, "oi": 500, "ltp": 47},
                {"strike": 25250, "oi": 200, "ltp": 76},
            ],
        },
    }


def test_ready_snapshot_metrics():
    result = analyse_live_market(snapshot())
    assert result["status"] == "READY"
    assert result["atm_strike"] == 25200
    assert result["call_wall"] == 25250
    assert result["put_wall"] == 25150
    assert result["pcr_oi"] > 1
    assert result["live_orders_enabled"] is False


def test_stale_snapshot_blocks_trading():
    result = analyse_live_market(snapshot(age=120), max_age_sec=30)
    assert result["status"] == "BLOCKED"
    assert result["recommended_action"] == "NO_TRADE"
    assert any("stale" in item.lower() for item in result["blockers"])


def test_empty_snapshot_is_blocked():
    result = analyse_live_market({"timestamp": datetime.now(timezone.utc).isoformat(), "spot": 25200, "chain": {}})
    assert result["status"] == "BLOCKED"
    assert "Option chain is empty" in result["blockers"]
