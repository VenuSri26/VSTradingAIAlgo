from datetime import datetime, timedelta, timezone

import app.kite_ticker_runtime as module
from app.kite_ticker_runtime import KiteTickerRuntime


class FakeTicker:
    MODE_FULL = "full"
    def __init__(self):
        self.subscribed = []
        self.mode = None
        self.closed = False
    def connect(self, threaded=False):
        self.threaded = threaded
    def subscribe(self, tokens):
        self.subscribed = list(tokens)
    def set_mode(self, mode, tokens):
        self.mode = (mode, list(tokens))
    def close(self):
        self.closed = True


def configure_live(monkeypatch):
    monkeypatch.setattr(module.settings, "trading_mode", "live")
    monkeypatch.setattr(module.settings, "kite_websocket_requested", True)
    monkeypatch.setattr(module.settings, "kite_api_key", "key")
    monkeypatch.setattr(module.settings, "kite_access_token", "token")


def test_runtime_connects_subscribes_and_ingests(monkeypatch):
    configure_live(monkeypatch)
    fake = FakeTicker()
    seen = []
    runtime = KiteTickerRuntime(heartbeat_timeout_sec=30, reconnect_base_sec=2, reconnect_max_sec=20)
    runtime.configure_contracts([{"instrument_token": 123, "tradingsymbol": "NIFTYCE", "option_type": "CE", "strike": 25200}])
    runtime.start(factory=lambda a, b: fake, ingest=lambda tick: seen.append(tick) or {"status": "ACCEPTED"})
    fake.on_connect(fake, {})
    assert fake.subscribed == [123]
    fake.on_ticks(fake, [{"instrument_token": 123, "last_price": 100.5, "exchange_timestamp": datetime.now(timezone.utc)}])
    assert seen[0]["ltp"] == 100.5
    assert runtime.status()["connected"] is True
    assert runtime.status()["live_orders_enabled"] is False


def test_exponential_reconnect_schedule(monkeypatch):
    configure_live(monkeypatch)
    runtime = KiteTickerRuntime(heartbeat_timeout_sec=30, reconnect_base_sec=2, reconnect_max_sec=20)
    runtime.start(factory=lambda a, b: (_ for _ in ()).throw(RuntimeError("network")), ingest=lambda x: x)
    first = runtime.status()
    assert first["reconnect_attempts"] == 1
    assert first["reconnect_delay_sec"] == 2
    runtime.monitor_once(datetime.fromisoformat(first["next_reconnect_at"]) + timedelta(seconds=1))
    second = runtime.status()
    assert second["reconnect_attempts"] == 2
    assert second["reconnect_delay_sec"] == 4


def test_heartbeat_timeout_falls_back(monkeypatch):
    configure_live(monkeypatch)
    fake = FakeTicker()
    runtime = KiteTickerRuntime(heartbeat_timeout_sec=5, reconnect_base_sec=1, reconnect_max_sec=10)
    runtime.configure_contracts([{"instrument_token": 123, "tradingsymbol": "NIFTYCE", "option_type": "CE", "strike": 25200}])
    runtime.start(factory=lambda a, b: fake, ingest=lambda x: {"status": "ACCEPTED"})
    fake.on_connect(fake, {})
    old = datetime.now(timezone.utc) - timedelta(seconds=10)
    runtime._state.last_callback_at = old.isoformat()
    status = runtime.monitor_once(datetime.now(timezone.utc))
    assert status["connected"] is False
    assert status["transport"] == "REST_FALLBACK"
    assert "heartbeat timeout" in status["last_error"]


def test_disabled_runtime_never_connects(monkeypatch):
    monkeypatch.setattr(module.settings, "trading_mode", "mock")
    monkeypatch.setattr(module.settings, "kite_websocket_requested", True)
    runtime = KiteTickerRuntime(heartbeat_timeout_sec=30, reconnect_base_sec=2, reconnect_max_sec=20)
    status = runtime.start(factory=lambda a, b: FakeTicker(), ingest=lambda x: x)
    assert status["running"] is False
    assert status["transport"] == "REST_FALLBACK"
