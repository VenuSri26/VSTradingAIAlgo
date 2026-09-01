from datetime import datetime, timezone

from app.live_paper_bridge import build_paper_setup_candidate


def snapshot():
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
