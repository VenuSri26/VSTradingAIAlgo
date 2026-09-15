from datetime import datetime, timezone

from app.data_quality_gate import evaluate_order_quote, evaluate_runtime_quality


def test_runtime_gate_fails_closed_on_stale_tick():
    market = {"fresh": True, "age_sec": 1.0, "authenticated": True, "instruments_synced": 20, "expiry": "2026-09-03"}
    runtime = {"connected": True, "transport": "WEBSOCKET", "last_tick_at": "2020-01-01T00:00:00+00:00", "next_reconnect_at": None}
    result = evaluate_runtime_quality(market, runtime, max_age_sec=5.0, websocket_required=True)
    assert result.approved is False
    assert "KITE_TICK_STALE" in result.blockers


def test_runtime_gate_blocks_reconnecting_feed():
    now = datetime.now(timezone.utc).isoformat()
    market = {"fresh": True, "age_sec": 1.0, "authenticated": True, "instruments_synced": 20, "expiry": "2026-09-03"}
    runtime = {"connected": False, "transport": "REST_FALLBACK", "last_tick_at": now, "next_reconnect_at": now}
    result = evaluate_runtime_quality(market, runtime, max_age_sec=5.0, websocket_required=True)
    assert result.approved is False
    assert "KITE_WEBSOCKET_NOT_HEALTHY" in result.blockers
    assert "KITE_RECONNECTING" in result.blockers


def test_quote_gate_blocks_wide_spread():
    order = {"tradingsymbol": "NIFTY26SEP25000CE", "quantity": 65}
    snapshot = {"chain": {"CE": [{
        "tradingsymbol": "NIFTY26SEP25000CE", "bid": 90.0, "ask": 100.0,
        "volume": 1000, "lot_size": 65, "quote_timestamp": None,
    }], "PE": []}}
    result = evaluate_order_quote(order, snapshot, max_spread_pct=3.0)
    assert result.approved is False
    assert "SPREAD_TOO_WIDE" in result.blockers


def test_quote_gate_uses_live_contract_lot_size():
    order = {"tradingsymbol": "NIFTY26SEP25000CE", "quantity": 75}
    snapshot = {"chain": {"CE": [{
        "tradingsymbol": "NIFTY26SEP25000CE", "bid": 99.5, "ask": 100.0,
        "volume": 1000, "lot_size": 65, "quote_timestamp": None,
    }], "PE": []}}
    result = evaluate_order_quote(order, snapshot, max_spread_pct=3.0)
    assert result.approved is False
    assert "INVALID_LIVE_LOT_SIZE" in result.blockers


def test_quote_gate_blocks_missing_quote_timestamp():
    order = {"tradingsymbol": "NIFTY26SEP25000CE", "quantity": 65}
    snapshot = {"chain": {"CE": [{
        "tradingsymbol": "NIFTY26SEP25000CE", "bid": 99.5, "ask": 100.0,
        "volume": 1000, "lot_size": 65, "quote_timestamp": None,
    }], "PE": []}}
    result = evaluate_order_quote(order, snapshot, max_spread_pct=3.0)
    assert result.approved is False
    assert "OPTION_QUOTE_TIMESTAMP_UNAVAILABLE" in result.blockers
