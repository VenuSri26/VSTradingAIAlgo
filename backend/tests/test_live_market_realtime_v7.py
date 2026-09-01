from datetime import datetime, timezone

import pandas as pd

import app.live_market_realtime as realtime_module
from app.data_sources.zerodha_client import NIFTY_INSTRUMENT_TOKEN
from app.live_market_realtime import LiveMarketRealtime
from app.live_market_stream import LiveMarketStream


class FakeRuntime:
    def status(self):
        return {"transport": "WEBSOCKET", "connected": True, "running": True, "subscription_count": 20, "last_tick_at": None}


class FakeSource:
    def get_ohlc(self, timeframe, lookback):
        n = max(60, lookback) if timeframe == "3m" else 5
        freq = "3min" if timeframe == "3m" else "D"
        idx = pd.date_range("2026-08-01", periods=n, freq=freq, tz="UTC")
        base = pd.Series(range(n), index=idx, dtype=float) + 25000
        return pd.DataFrame({"open": base, "high": base + 10, "low": base - 10, "close": base + 2, "volume": 1000.0}, index=idx)


def test_realtime_feed_uses_stream_values(monkeypatch):
    stream = LiveMarketStream()
    monkeypatch.setattr(realtime_module, "get_live_market_stream", lambda: stream)
    engine = LiveMarketRealtime(FakeSource(), FakeRuntime())
    stream.ingest({"instrument_token": NIFTY_INSTRUMENT_TOKEN, "ltp": 25200, "exchange_timestamp": datetime.now(timezone.utc).isoformat(), "asset_type": "NIFTY_INDEX"})
    feed = engine.feed()
    assert feed["nifty_spot"] == 25200
    assert feed["transport"] == "WEBSOCKET"
    assert feed["live_orders_enabled"] is False


def test_indicators_use_completed_zerodha_ohlc_during_stream_warmup(monkeypatch):
    stream = LiveMarketStream()
    monkeypatch.setattr(realtime_module, "get_live_market_stream", lambda: stream)
    result = LiveMarketRealtime(FakeSource(), FakeRuntime()).indicators(lookback=120)
    assert result["status"] == "READY"
    assert result["source"] == "ZERODHA_COMPLETED_OHLC"
    assert result["indicators"]["ema20"] > 0
    assert "STREAM_WARMUP_USING_COMPLETED_ZERODHA_OHLC" in result["warnings"]


def test_candle_endpoint_model_never_enables_live_orders(monkeypatch):
    stream = LiveMarketStream()
    monkeypatch.setattr(realtime_module, "get_live_market_stream", lambda: stream)
    result = LiveMarketRealtime(FakeSource(), FakeRuntime()).candles(timeframe="3m")
    assert result["source"] == "KITE_TICKER_STREAM"
    assert result["live_orders_enabled"] is False
