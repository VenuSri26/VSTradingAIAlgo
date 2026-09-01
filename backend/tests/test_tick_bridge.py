from datetime import datetime, timedelta, timezone

from app.tick_bridge import TickBridge


def _tick(ts, ltp=100.0, sequence=1):
    return {
        "instrument_token": 123,
        "tradingsymbol": "NIFTY26AUG25200CE",
        "option_type": "CE",
        "strike": 25200,
        "ltp": ltp,
        "exchange_timestamp": ts,
        "sequence": sequence,
    }


def test_accepts_and_restores_tick_history(tmp_path):
    path = tmp_path / "ticks.jsonl"
    now = datetime.now(timezone.utc)
    bridge = TickBridge(str(path))
    result = bridge.ingest(_tick(now.isoformat()))
    assert result["status"] == "ACCEPTED"
    assert bridge.status()["accepted"] == 1
    restored = TickBridge(str(path))
    assert restored.status()["history_size"] == 1
    assert restored.history(1)[0]["ltp"] == 100.0


def test_rejects_duplicate_and_out_of_order_ticks(tmp_path):
    now = datetime.now(timezone.utc)
    bridge = TickBridge(str(tmp_path / "ticks.jsonl"))
    assert bridge.ingest(_tick(now.isoformat(), 100, 1))["status"] == "ACCEPTED"
    duplicate = bridge.ingest(_tick(now.isoformat(), 100, 1))
    assert duplicate["reason"] == "DUPLICATE_TICK"
    older = bridge.ingest(_tick((now - timedelta(seconds=1)).isoformat(), 99, 0))
    assert older["reason"] == "OUT_OF_ORDER_TICK"


def test_routes_matching_tick_to_paper_monitor(tmp_path):
    now = datetime.now(timezone.utc)
    bridge = TickBridge(str(tmp_path / "ticks.jsonl"))
    trade = {"id": 1, "option_type": "CE", "strike": 25200}
    calls = []

    def monitor(open_trade, price):
        calls.append((open_trade["id"], price))
        return {"action": "HOLD"}

    result = bridge.ingest(_tick(now.isoformat(), 105, 2), open_trade=trade, monitor=monitor)
    assert result["status"] == "ACCEPTED"
    assert result["paper_action"]["action"] == "HOLD"
    assert calls == [(1, 105.0)]
    assert bridge.status()["routed_to_paper"] == 1
