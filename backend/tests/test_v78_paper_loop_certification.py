"""Deterministic, broker-free certification of the complete v7.8 paper loop."""
from datetime import datetime, timezone

from app import store
from app.config import settings
from app.paper_auto_trader import run_once
from app.paper_journal import daily_summary, journal_rows
from app.paper_monitor import monitor_once


class ScenarioSource:
    def __init__(self, price=100.0, timestamp="2026-09-28T04:30:00+00:00"):
        self.price = price
        self.timestamp = timestamp

    def get_option_chain(self, atm_range=8):
        return {
            "timestamp": self.timestamp,
            "spot": 25210,
            "expiry": "2026-10-01",
            "chain": {
                "CE": [{"strike": 25200, "oi": 500, "ltp": self.price,
                        "quote_timestamp": self.timestamp}],
                "PE": [{"strike": 25200, "oi": 1000, "ltp": 92,
                        "quote_timestamp": self.timestamp}],
            },
        }


def test_complete_autonomous_paper_lifecycle_survives_state_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "certification.db"))
    monkeypatch.setattr(settings, "paper_notification_path", str(tmp_path / "paper.jsonl"))
    monkeypatch.setattr(settings, "paper_auto_trader_enabled", True)
    monkeypatch.setattr(settings, "live_orders_enabled", False)
    monkeypatch.setattr(settings, "paper_auto_trader_min_score", 70)
    monkeypatch.setattr(settings, "paper_auto_trader_grades", "A,A+")
    monkeypatch.setattr(settings, "paper_capital", 100000.0)
    monkeypatch.setattr(settings, "max_risk_per_trade_pct", 5.0)
    monkeypatch.setattr(settings, "max_capital_utilization_pct", 80.0)
    monkeypatch.setattr(settings, "risk_cooldown_minutes", 0)
    monkeypatch.setattr(settings, "nifty_lot_size", 65)
    monkeypatch.setattr(settings, "paper_monitor_max_age_sec", 30)

    opened_at = datetime(2026, 9, 28, 4, 30, tzinfo=timezone.utc)
    opened = run_once(
        ScenarioSource(), opened_at,
        trend_provider=lambda **_: {"trend": "BULLISH_STRENGTHENING"},
    )
    assert opened["action"] == "PAPER_TRADE_OPENED"
    trade_id = opened["trade_id"]

    # The monitor recovers solely from SQLite, which models a process restart:
    # no in-memory trade object is carried from the entry worker.
    managed_at = datetime(2026, 9, 28, 4, 31, tzinfo=timezone.utc)
    managed = monitor_once(ScenarioSource(105, managed_at.isoformat()), now=managed_at)
    assert managed["action"] == "HOLD"
    assert store.get_open_paper_trade()["id"] == trade_id

    closed_at = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)  # 15:30 IST
    closed = monitor_once(
        ScenarioSource(105, closed_at.isoformat()), now=closed_at
    )
    assert closed["action"] == "CLOSED"
    assert closed["status"] == "CLOSED_EOD"
    assert store.get_open_paper_trade() is None

    rows = journal_rows()
    assert rows[0]["trade_id"] == trade_id
    assert rows[0]["status"] == "CLOSED_EOD"
    assert rows[0]["net_pnl"] is not None
    summary = daily_summary()
    assert summary["journal_entries"] == 1
    assert summary["broker_orders_sent"] is False
    assert store.paper_automation_summary()["paper_trades_opened"] == 1
