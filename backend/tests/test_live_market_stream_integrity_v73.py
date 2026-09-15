from datetime import datetime, timedelta, timezone

from app.data_sources.zerodha_client import NIFTY_INSTRUMENT_TOKEN
from app.live_market_stream import LiveMarketStream


def _tick(price, ts, sequence=0):
    return {
        "instrument_token": NIFTY_INSTRUMENT_TOKEN,
        "ltp": price,
        "exchange_timestamp": ts.isoformat(),
        "volume": 100,
        "asset_type": "NIFTY_INDEX",
        "sequence": sequence,
    }


def test_duplicate_tick_is_rejected_before_candle_mutation():
    stream = LiveMarketStream()
    ts = datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)
    assert stream.ingest(_tick(25000, ts, 1))["status"] == "ACCEPTED"
    result = stream.ingest(_tick(25000, ts, 1))
    assert result == {"status": "IGNORED", "reason": "DUPLICATE_TICK"}
    assert stream.candles("1m")[-1]["ticks"] == 1
    assert stream.status()["duplicate_ticks"] == 1


def test_late_tick_cannot_reopen_closed_three_minute_bar():
    stream = LiveMarketStream()
    base = datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)
    stream.ingest(_tick(25000, base, 1))
    stream.ingest(_tick(25020, base + timedelta(minutes=3), 2))
    before = stream.candles("3m", include_current=True)
    assert len(before) == 2
    result = stream.ingest(_tick(24000, base + timedelta(minutes=1), 3))
    assert result == {"status": "IGNORED", "reason": "OUT_OF_ORDER_TICK"}
    after = stream.candles("3m", include_current=True)
    assert after == before
    assert stream.status()["out_of_order_ticks"] == 1
