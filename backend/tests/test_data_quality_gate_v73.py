from datetime import datetime, timedelta, timezone

from app.data_quality_gate import evaluate_order_quote, evaluate_runtime_quality
from app.config import settings


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


def test_runtime_gate_fails_closed_when_consensus_is_required(monkeypatch):
    monkeypatch.setattr(settings, "market_data_consensus_required", True)
    market = {
        "fresh": True, "age_sec": 1.0, "authenticated": True,
        "instruments_synced": 20, "expiry": "2026-09-03",
        "source_consensus": {"status": "DEGRADED", "approved": False},
    }
    result = evaluate_runtime_quality(market, None, max_age_sec=5.0, websocket_required=False)
    assert result.approved is False
    assert "SOURCE_CONSENSUS_DEGRADED" in result.blockers


def test_runtime_gate_records_verified_consensus(monkeypatch):
    monkeypatch.setattr(settings, "market_data_consensus_required", True)
    market = {
        "fresh": True, "age_sec": 1.0, "authenticated": True,
        "instruments_synced": 20, "expiry": "2026-09-03",
        "source_consensus": {"status": "VERIFIED", "approved": True},
    }
    result = evaluate_runtime_quality(market, None, max_age_sec=5.0, websocket_required=False)
    assert result.approved is True


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


def _verified_leg(**overrides):
    leg = {
        "tradingsymbol": "NIFTY99DEC25000CE",
        "exchange": "NFO",
        "segment": "NFO-OPT",
        "expiry": "2099-12-31",
        "option_type": "CE",
        "strike": 25000,
        "instrument_token": 123456,
        "lot_size": 65,
        "tick_size": 0.05,
        "bid": 99.5,
        "ask": 100.0,
        "volume": 1000,
        "quote_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    leg.update(overrides)
    return leg


def test_quote_gate_accepts_fully_verified_contract_identity():
    order = {
        "tradingsymbol": "NIFTY99DEC25000CE", "quantity": 65,
        "strike": 25000, "instrument_token": 123456,
    }
    snapshot = {"expiry": "2099-12-31", "chain": {"CE": [_verified_leg()], "PE": []}}
    result = evaluate_order_quote(order, snapshot, max_spread_pct=3.0)
    assert result.approved is True
    assert result.blockers == []


def test_quote_gate_blocks_expired_or_mismatched_expiry():
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    order = {"tradingsymbol": "NIFTY99DEC25000CE", "quantity": 65}
    snapshot = {"expiry": yesterday, "chain": {"CE": [_verified_leg(expiry=yesterday)], "PE": []}}
    result = evaluate_order_quote(order, snapshot)
    assert "CONTRACT_EXPIRY_INVALID" in result.blockers


def test_quote_gate_blocks_contract_master_identity_mismatch():
    order = {
        "tradingsymbol": "NIFTY99DEC25000CE", "quantity": 65,
        "strike": 25100, "instrument_token": 999,
    }
    snapshot = {"expiry": "2099-12-31", "chain": {"CE": [
        _verified_leg(exchange="NSE", segment="NSE", option_type="PE", tick_size=0),
    ], "PE": []}}
    result = evaluate_order_quote(order, snapshot)
    assert "CONTRACT_VENUE_MISMATCH" in result.blockers
    assert "CONTRACT_OPTION_TYPE_MISMATCH" in result.blockers
    assert "CONTRACT_TOKEN_MISMATCH" in result.blockers
    assert "CONTRACT_STRIKE_MISMATCH" in result.blockers
    assert "CONTRACT_TICK_SIZE_INVALID" in result.blockers


def test_quote_gate_blocks_duplicate_contract_symbol():
    order = {"tradingsymbol": "NIFTY99DEC25000CE", "quantity": 65}
    snapshot = {
        "expiry": "2099-12-31",
        "chain": {"CE": [_verified_leg(), _verified_leg(instrument_token=654321)], "PE": []},
    }
    result = evaluate_order_quote(order, snapshot)
    assert result.blockers == ["AMBIGUOUS_CONTRACT_IDENTITY"]
