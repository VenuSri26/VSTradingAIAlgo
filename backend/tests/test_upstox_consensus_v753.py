from datetime import datetime, timedelta, timezone

from app.consensus_certification import certify_consensus_shadow
from app.upstox_market_data import UPSTOX_FULL_QUOTE_URL, UpstoxV3QuoteAdapter


class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): return None
    def json(self): return self.payload


def test_upstox_adapter_parses_official_full_quote_shape_and_is_read_only():
    now = datetime.now(timezone.utc) - timedelta(seconds=1)
    calls = []
    def fetcher(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"status": "success", "data": {"NSE_INDEX:Nifty 50": {
            "instrument_token": "NSE_INDEX|Nifty 50",
            "last_price": 25123.45,
            "last_trade_time": int(now.timestamp() * 1000),
        }}})
    adapter = UpstoxV3QuoteAdapter("secret", fetcher=fetcher)
    quote = adapter.latest("NIFTY 50")
    assert quote.source == "UPSTOX_V3"
    assert quote.provider_instrument_id == "NSE_INDEX|Nifty 50"
    assert quote.last_price == 25123.45
    assert calls[0][0] == UPSTOX_FULL_QUOTE_URL
    assert calls[0][1]["headers"]["Authorization"] == "Bearer secret"
    assert adapter.status()["broker_order_capability"] is False


def test_upstox_adapter_fails_closed_without_trade_timestamp():
    adapter = UpstoxV3QuoteAdapter("secret", fetcher=lambda *a, **k: FakeResponse({
        "status": "success", "data": {"x": {"last_price": 25000}}
    }))
    assert adapter.latest("NIFTY 50") is None
    assert "last_trade_time" in adapter.status()["last_error"]


def test_upstox_adapter_outage_returns_last_evidence_without_breaking_primary():
    now = datetime.now(timezone.utc) - timedelta(seconds=1)
    outcomes = [FakeResponse({"status": "success", "data": {"x": {
        "last_price": 25000, "last_trade_time": int(now.timestamp() * 1000)
    }}}), RuntimeError("provider down")]
    def fetcher(*args, **kwargs):
        item = outcomes.pop(0)
        if isinstance(item, Exception): raise item
        return item
    adapter = UpstoxV3QuoteAdapter("secret", poll_interval_sec=1, fetcher=fetcher)
    first = adapter.latest("NIFTY 50")
    adapter._last_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=2)
    assert adapter.latest("NIFTY 50") == first
    assert "provider down" in adapter.status()["last_error"]


def row(day, status="VERIFIED", deviation=0.02):
    return {
        "status": status,
        "primary_exchange_timestamp": f"2026-09-{day:02d}T05:00:00+00:00",
        "deviation_pct": deviation,
    }


def test_consensus_certification_passes_only_with_multisession_evidence():
    result = certify_consensus_shadow(
        [row(10), row(11), row(12)], min_samples=3, min_sessions=3,
        min_verified_ratio=.98, max_conflict_ratio=.01, max_stale_ratio=.01,
        max_p95_deviation_pct=.08,
    )
    assert result["certified"] is True
    assert result["metrics"]["p95_deviation_pct"] == .02
    assert result["automatic_enforcement_change"] is False


def test_consensus_certification_explains_failed_promotion():
    result = certify_consensus_shadow(
        [row(10, "CONFLICTED", .20), row(10, "STALE", None)],
        min_samples=10, min_sessions=3, min_verified_ratio=.98,
        max_conflict_ratio=.01, max_stale_ratio=.01, max_p95_deviation_pct=.08,
    )
    assert result["certified"] is False
    assert "INSUFFICIENT_CONSENSUS_SAMPLES" in result["blockers"]
    assert "CONFLICT_RATIO_ABOVE_THRESHOLD" in result["blockers"]
    assert "P95_DEVIATION_ABOVE_THRESHOLD" in result["blockers"]
