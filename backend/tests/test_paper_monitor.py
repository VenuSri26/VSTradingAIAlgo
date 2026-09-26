from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import store
from app.config import settings
from app.paper_monitor import monitor_once


class QuoteSource:
    def __init__(self, price: float, timestamp: str = "2026-08-02T04:30:00+00:00"):
        self.price = price
        self.timestamp = timestamp

    def get_option_chain(self, atm_range: int = 20):
        return {
            "chain": {"CE": [{"strike": 25000, "ltp": self.price, "quote_timestamp": self.timestamp}], "PE": []}
        }


def _payload():
    return {"timestamp":"2026-08-02T10:00:00+00:00","decision":{"decision":"CE_BUY","grade":"A","alignment_score":80,"explanation":"x","plan":{"option_type":"CE","strike":25000,"entry_low":100,"entry_high":105,"stop_loss":90,"target_1":120,"target_2":140,"risk_reward":2}}}


def _open_trade(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "monitor.db"))
    # Isolate the notification outbox too: monitor_once writes MANAGED/CLOSED
    # events straight to settings.paper_notification_path, which otherwise
    # defaults to the real backend/data/paper_notifications.jsonl file.
    monkeypatch.setattr(settings, "paper_notification_path", str(tmp_path / "notifications.jsonl"))
    setup_id = store.create_trade_setup("monitor-1", _payload())
    store.review_trade_setup(setup_id, "APPROVED", "ok")
    return store.open_paper_trade(setup_id, 75, 100, 0)


def test_monitor_holds_and_records_event(tmp_path, monkeypatch):
    trade_id = _open_trade(tmp_path, monkeypatch)
    result = monitor_once(QuoteSource(110), now=datetime(2026, 8, 2, 4, 30, tzinfo=timezone.utc))
    assert result["action"] == "HOLD"
    events = store.list_paper_monitor_events(trade_id)
    assert events[0]["action"] == "HOLD"


def test_monitor_target_one_moves_single_lot_to_breakeven(tmp_path, monkeypatch):
    trade_id = _open_trade(tmp_path, monkeypatch)
    result = monitor_once(QuoteSource(121), now=datetime(2026, 8, 2, 4, 30, tzinfo=timezone.utc))
    assert result["action"] == "MANAGED"
    assert result["remaining_quantity"] == 75
    assert result["active_stop_loss"] >= 100
    assert store.get_open_paper_trade() is not None
    assert store.list_paper_monitor_events(trade_id)[0]["action"] == "MANAGED"


def test_monitor_forces_eod_exit(tmp_path, monkeypatch):
    _open_trade(tmp_path, monkeypatch)
    result = monitor_once(
        QuoteSource(105, "2026-08-02T09:55:00+00:00"),
        now=datetime(2026, 8, 2, 9, 55, tzinfo=timezone.utc),
    )
    assert result["status"] == "CLOSED_EOD"


def test_monitor_blocks_stale_quote_without_closing_trade(tmp_path, monkeypatch):
    trade_id = _open_trade(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "paper_monitor_max_age_sec", 30)
    result = monitor_once(
        QuoteSource(1, "2026-08-02T09:58:00+00:00"),
        now=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc),
    )
    assert result["action"] == "ERROR"
    assert "stale" in result["detail"]
    assert store.get_open_paper_trade()["id"] == trade_id


def test_monitor_blocks_missing_quote_timestamp(tmp_path, monkeypatch):
    trade_id = _open_trade(tmp_path, monkeypatch)
    result = monitor_once(
        QuoteSource(1, ""),
        now=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc),
    )
    assert result["action"] == "ERROR"
    assert "timestamp is missing" in result["detail"]
    assert store.get_open_paper_trade()["id"] == trade_id
