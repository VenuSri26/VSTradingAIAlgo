from datetime import datetime, timezone

from app.live_paper_bridge import build_paper_setup_candidate


def snapshot():
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "spot": 25210,
        "expiry": "2026-08-06",
        "chain": {
            "CE": [
                {"strike": 25200, "oi": 500, "volume": 1000, "ltp": 100, "bid": 99, "ask": 101},
                {"strike": 25250, "oi": 900, "volume": 1000, "ltp": 72, "bid": 71, "ask": 73},
            ],
            "PE": [
                {"strike": 25200, "oi": 1000, "volume": 1000, "ltp": 92, "bid": 91, "ask": 93},
                {"strike": 25150, "oi": 700, "volume": 1000, "ltp": 65, "bid": 64, "ask": 66},
            ],
        },
    }


def test_bullish_trend_creates_ce_preview():
    result = build_paper_setup_candidate(snapshot(), {"trend": "BULLISH_STRENGTHENING"})
    assert result["status"] == "READY_FOR_HUMAN_REVIEW"
    assert result["candidate"]["option_type"] == "CE"
    assert result["candidate"]["strike"] == 25200
    assert result["live_orders_enabled"] is False


def test_bearish_trend_creates_pe_preview():
    result = build_paper_setup_candidate(snapshot(), {"trend": "BEARISH_STRENGTHENING"})
    assert result["status"] == "READY_FOR_HUMAN_REVIEW"
    assert result["candidate"]["option_type"] == "PE"


def test_neutral_trend_blocks_setup():
    result = build_paper_setup_candidate(snapshot(), {"trend": "STABLE"})
    assert result["status"] == "BLOCKED"
    assert result["candidate"] is None
    assert result["action"] == "NO_TRADE"


def test_wide_spread_blocks_setup():
    data = snapshot()
    data["chain"]["CE"][0].update(bid=80, ask=120)
    result = build_paper_setup_candidate(data, {"trend": "BULLISH_STRENGTHENING"})
    assert result["status"] == "BLOCKED"
    assert any("spread" in item for item in result["blockers"])
