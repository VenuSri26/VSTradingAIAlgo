from datetime import datetime, timedelta, timezone

from app.data_sources.zerodha_client import INDIA_VIX_TOKEN, NIFTY_INSTRUMENT_TOKEN
from app.live_market_stream import LiveMarketStream


def tick(token, price, ts, volume=0, asset_type=None):
    return {
        "instrument_token": token,
        "ltp": price,
        "exchange_timestamp": ts.isoformat(),
        "volume": volume,
        "asset_type": asset_type,
    }


def test_stream_stores_live_index_and_vix_ticks():
    stream = LiveMarketStream()
    now = datetime.now(timezone.utc)
    assert stream.ingest(tick(NIFTY_INSTRUMENT_TOKEN, 25100.5, now, asset_type="NIFTY_INDEX"))["status"] == "ACCEPTED"
    assert stream.ingest(tick(INDIA_VIX_TOKEN, 13.2, now, asset_type="INDIA_VIX"))["status"] == "ACCEPTED"
    status = stream.status()
    assert status["nifty_spot"] == 25100.5
    assert status["india_vix"] == 13.2
    assert status["live_orders_enabled"] is False


def test_stream_builds_1m_3m_5m_candles_from_nifty_ticks():
    stream = LiveMarketStream()
    base = datetime(2026, 8, 7, 4, 0, tzinfo=timezone.utc)
    stream.ingest(tick(NIFTY_INSTRUMENT_TOKEN, 25000, base, asset_type="NIFTY_INDEX"))
    stream.ingest(tick(NIFTY_INSTRUMENT_TOKEN, 25010, base + timedelta(seconds=20), asset_type="NIFTY_INDEX"))
    stream.ingest(tick(NIFTY_INSTRUMENT_TOKEN, 24995, base + timedelta(seconds=40), asset_type="NIFTY_INDEX"))
    candle = stream.candles("1m", 10)[-1]
    assert candle["open"] == 25000
    assert candle["high"] == 25010
    assert candle["low"] == 24995
    assert candle["close"] == 24995
    assert candle["ticks"] == 3
    assert len(stream.candles("3m", 10)) == 1
    assert len(stream.candles("5m", 10)) == 1


def test_stream_rejects_invalid_ticks_without_fabricating_values():
    stream = LiveMarketStream()
    assert stream.ingest({"instrument_token": 0, "ltp": 100})["status"] == "IGNORED"
    assert stream.ingest({"instrument_token": 123, "ltp": None})["status"] == "IGNORED"
    assert stream.status()["accepted_ticks"] == 0
    assert stream.status()["ignored_ticks"] == 2
