from datetime import datetime, timedelta, timezone

import pytest

from app.consensus_shadow import ConsensusShadowRecorder
from app.market_data_consensus import MarketDataEnvelopeV2, evaluate_source_consensus
from app.secondary_market_data import ReplaySecondaryQuoteAdapter


def quote(source: str, price: float, timestamp: datetime):
    return MarketDataEnvelopeV2.create(
        source=source, instrument="NIFTY 50", last_price=price,
        exchange_timestamp=timestamp, received_at=timestamp,
    )


def test_replay_adapter_persists_and_restores_latest_quote(tmp_path):
    path = tmp_path / "secondary.jsonl"
    now = datetime.now(timezone.utc)
    adapter = ReplaySecondaryQuoteAdapter(str(path))
    adapter.ingest(quote("SECONDARY", 25000, now).to_dict())
    restored = ReplaySecondaryQuoteAdapter(str(path))
    assert restored.latest("NIFTY 50").last_price == 25000
    assert restored.status()["broker_order_capability"] is False


def test_replay_adapter_rejects_duplicate_or_older_quote(tmp_path):
    now = datetime.now(timezone.utc)
    adapter = ReplaySecondaryQuoteAdapter(str(tmp_path / "secondary.jsonl"))
    adapter.ingest(quote("SECONDARY", 25000, now).to_dict())
    with pytest.raises(ValueError, match="newer exchange timestamp"):
        adapter.ingest(quote("SECONDARY", 25001, now - timedelta(seconds=1)).to_dict())


def test_shadow_recorder_is_durable_and_duplicate_safe(tmp_path):
    now = datetime.now(timezone.utc)
    primary = quote("ZERODHA", 25000, now)
    secondary = quote("SECONDARY", 25010, now)
    decision = evaluate_source_consensus([primary, secondary], now=now)
    path = tmp_path / "shadow.jsonl"
    recorder = ConsensusShadowRecorder(str(path))
    assert recorder.record(primary, decision)["recorded"] is True
    assert recorder.record(primary, decision)["recorded"] is False
    summary = ConsensusShadowRecorder(str(path)).summary()
    assert summary["samples"] == 1
    assert summary["verified_ratio"] == 1.0
    assert summary["live_orders_enabled"] is False
