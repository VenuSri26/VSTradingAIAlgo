from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace

import pandas as pd

from app.config import settings
from app.live_market_engine import LiveMarketEngine


class FakeRuntime:
    def __init__(self, connected=True):
        self.connected = connected
    def status(self):
        return {"enabled": True, "connected": self.connected, "transport": "WEBSOCKET" if self.connected else "REST_FALLBACK", "subscription_count": 6, "last_tick_at": "2026-08-06T10:00:00+00:00"}


class FakeSupervisor:
    def snapshot(self):
        return {"authenticated": True, "connected": True, "fresh": True, "age_sec": 1.2}


class FakeSource:
    source_name = "ZERODHA"
    def get_spot(self): return 25125.0
    def get_vix(self): return 12.4
    def get_last_tick_timestamp(self): return "2026-08-06T10:00:00+00:00"
    def get_option_chain(self, atm_range=8):
        return {"spot":25125.0,"atm":25100,"expiry":"2026-08-13","chain":{"CE":[{"strike":25100,"oi":100,"oi_change":10,"ltp":100,"bid":99,"ask":101,"volume":1000}],"PE":[{"strike":25100,"oi":150,"oi_change":20,"ltp":90,"bid":89,"ask":91,"volume":1200}]}}
    def get_ohlc(self, timeframe, lookback):
        n=max(30, lookback if timeframe=="3m" else 5)
        idx=pd.date_range("2026-08-01", periods=n, freq="3min" if timeframe=="3m" else "D", tz="UTC")
        base=pd.Series(range(n), index=idx, dtype=float)+25000
        return pd.DataFrame({"open":base,"high":base+10,"low":base-10,"close":base+2,"volume":1000}, index=idx)


@contextmanager
def live_settings():
    old=(settings.trading_mode, settings.kite_websocket_requested)
    settings.trading_mode="live"; settings.kite_websocket_requested=True
    try: yield
    finally: settings.trading_mode, settings.kite_websocket_requested=old


def test_status_ready_for_live_zerodha():
    with live_settings():
        data=LiveMarketEngine(FakeSource(), FakeRuntime(), FakeSupervisor()).status()
    assert data["status"] == "READY"
    assert data["ready_for_live_data"] is True
    assert data["live_orders_enabled"] is False


def test_snapshot_contains_live_market_and_derived_analytics():
    with live_settings():
        data=LiveMarketEngine(FakeSource(), FakeRuntime(), FakeSupervisor()).snapshot()
    assert data["market"]["spot"] == 25125.0
    assert data["option_chain"]["summary"]["pcr_oi"] == 1.5
    assert data["indicators"]["ema20"] > 0
    assert data["recommended_action"] == "USE_FOR_DECISION_SUPPORT"


def test_mock_mode_is_explicitly_blocked_for_live_readiness():
    old=settings.trading_mode; settings.trading_mode="mock"
    try:
        data=LiveMarketEngine(FakeSource(), FakeRuntime(), FakeSupervisor()).status()
    finally:
        settings.trading_mode=old
    assert data["status"] == "BLOCKED"
    assert "TRADING_MODE_NOT_LIVE" in data["blockers"]
