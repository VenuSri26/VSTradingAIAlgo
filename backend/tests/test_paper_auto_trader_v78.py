from __future__ import annotations

from datetime import datetime, timezone

from app import store
from app.config import settings
from app.paper_auto_trader import run_once
from app.live_intelligence_history import list_history


class Source:
    timestamp = datetime.now(timezone.utc).isoformat()

    def get_option_chain(self, atm_range=8):
        return {
            "timestamp": self.timestamp,
            "spot": 25210,
            "expiry": "2026-10-01",
            "chain": {
                "CE": [{"strike": 25200, "oi": 500, "ltp": 100}],
                "PE": [{"strike": 25200, "oi": 1000, "ltp": 92}],
            },
        }


class BrokenSource:
    def get_option_chain(self, atm_range=8):
        raise RuntimeError("token expired")


def _configure(monkeypatch):
    monkeypatch.setattr(settings, "paper_auto_trader_enabled", True)
    monkeypatch.setattr(settings, "live_orders_enabled", False)
    monkeypatch.setattr(settings, "paper_auto_trader_min_score", 70)
    monkeypatch.setattr(settings, "paper_auto_trader_grades", "A,A+")
    monkeypatch.setattr(settings, "paper_capital", 100000.0)
    monkeypatch.setattr(settings, "max_risk_per_trade_pct", 5.0)
    monkeypatch.setattr(settings, "max_capital_utilization_pct", 80.0)
    monkeypatch.setattr(settings, "risk_cooldown_minutes", 0)
    monkeypatch.setattr(settings, "nifty_lot_size", 65)


def test_auto_trader_opens_paper_trade_only(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "auto.db"))
    _configure(monkeypatch)
    now = datetime(2026, 9, 28, 4, 30, tzinfo=timezone.utc)  # 10:00 IST Monday

    result = run_once(Source(), now, trend_provider=lambda **_: {"trend": "BULLISH_STRENGTHENING"})

    assert result["action"] == "PAPER_TRADE_OPENED"
    assert result["execution_mode"] == "PAPER_ONLY"
    assert result["live_orders_enabled"] is False
    assert store.get_open_paper_trade()["option_type"] == "CE"
    assert len(list_history()) == 1


def test_auto_trader_waits_when_market_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "closed.db"))
    _configure(monkeypatch)
    saturday = datetime(2026, 9, 26, 4, 30, tzinfo=timezone.utc)

    result = run_once(BrokenSource(), saturday)

    assert result["action"] == "WAITING"
    assert result["reason"] == "WEEKEND"


def test_auto_trader_fails_closed_on_broker_error(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "broken.db"))
    _configure(monkeypatch)
    now = datetime(2026, 9, 28, 4, 30, tzinfo=timezone.utc)

    result = run_once(BrokenSource(), now)

    assert result["action"] == "BLOCKED"
    assert "BROKER_DATA_UNAVAILABLE" in result["reason"]
    assert store.get_open_paper_trade() is None


def test_auto_trader_refuses_when_live_orders_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "safety.db"))
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "live_orders_enabled", True)
    now = datetime(2026, 9, 28, 4, 30, tzinfo=timezone.utc)

    result = run_once(Source(), now)

    assert result["action"] == "BLOCKED"
    assert "LIVE_ORDERS_ENABLED" in result["reason"]


def test_auto_trader_processes_each_three_minute_candle_once(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "dedupe.db"))
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "paper_auto_trader_min_score", 101)
    now = datetime(2026, 9, 28, 4, 30, tzinfo=timezone.utc)
    source = Source()

    first = run_once(source, now, trend_provider=lambda **_: {"trend": "BULLISH_STRENGTHENING"})
    second = run_once(source, now, trend_provider=lambda **_: {"trend": "BULLISH_STRENGTHENING"})

    assert first["action"] == "NO_TRADE"
    assert second["action"] == "WAITING"
    assert second["reason"] == "CANDLE_ALREADY_PROCESSED"
