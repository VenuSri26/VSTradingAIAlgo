from datetime import datetime, timedelta, timezone

import pytest

from app.market_data_consensus import (
    ConsensusStatus,
    MarketDataEnvelopeV2,
    evaluate_source_consensus,
)


NOW = datetime(2026, 9, 16, 4, 30, tzinfo=timezone.utc)


def envelope(source: str, price: float, *, age_sec: float = 1.0):
    return MarketDataEnvelopeV2.create(
        source=source,
        instrument="NIFTY 50",
        last_price=price,
        exchange_timestamp=NOW - timedelta(seconds=age_sec),
        received_at=NOW,
    )


def test_consensus_verifies_independent_fresh_sources_within_tolerance():
    result = evaluate_source_consensus(
        [envelope("ZERODHA", 25000), envelope("SECONDARY", 25010)],
        now=NOW,
        max_price_deviation_pct=0.15,
    )
    assert result.status == ConsensusStatus.VERIFIED
    assert result.approved is True
    assert result.evidence["observed_sources"] == ["SECONDARY", "ZERODHA"]


def test_consensus_fails_closed_on_price_conflict():
    result = evaluate_source_consensus(
        [envelope("ZERODHA", 25000), envelope("SECONDARY", 25100)],
        now=NOW,
        max_price_deviation_pct=0.15,
    )
    assert result.status == ConsensusStatus.CONFLICTED
    assert result.approved is False
    assert "CONSENSUS_PRICE_CONFLICT" in result.blockers


def test_consensus_is_degraded_with_only_one_source():
    result = evaluate_source_consensus([envelope("ZERODHA", 25000)], now=NOW)
    assert result.status == ConsensusStatus.DEGRADED
    assert result.approved is False
    assert "CONSENSUS_INSUFFICIENT_INDEPENDENT_SOURCES" in result.warnings


def test_consensus_fails_closed_when_all_sources_are_stale():
    result = evaluate_source_consensus(
        [envelope("ZERODHA", 25000, age_sec=60), envelope("SECONDARY", 25000, age_sec=60)],
        now=NOW,
        max_age_sec=10,
    )
    assert result.status == ConsensusStatus.STALE
    assert "CONSENSUS_ALL_SOURCES_STALE" in result.blockers


def test_envelope_rejects_crossed_quote_and_naive_timestamp():
    with pytest.raises(ValueError, match="crossed quote"):
        MarketDataEnvelopeV2.create(
            source="ZERODHA", instrument="NIFTY 50", last_price=25000,
            bid=101, ask=100, exchange_timestamp=NOW, received_at=NOW,
        )
    with pytest.raises(ValueError, match="timezone"):
        MarketDataEnvelopeV2.create(
            source="ZERODHA", instrument="NIFTY 50", last_price=25000,
            exchange_timestamp="2026-09-16T04:30:00", received_at=NOW,
        )
