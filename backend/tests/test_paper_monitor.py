from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import store
from app.paper_monitor import monitor_once


class QuoteSource:
    def __init__(self, price: float):
        self.price = price

    def get_option_chain(self, atm_range: int = 20):
        return {
            "chain": {"CE": [{"strike": 25000, "ltp": self.price, "quote_timestamp": "2026-08-02T10:00:00+00:00"}], "PE": []}
        }


def _payload():
    return {"timestamp":"2026-08-02T10:00:00+00:00","decision":{"decision":"CE_BUY","grade":"A","alignment_score":80,"explanation":"x","plan":{"option_type":"CE","strike":25000,"entry_low":100,"entry_high":105,"stop_loss":90,"target_1":120,"target_2":140,"risk_reward":2}}}


def _open_trade(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "monitor.db"))
    setup_id = store.create_trade_setup("monitor-1", _payload())
    store.review_trade_setup(setup_id, "APPROVED", "ok")
    return store.open_paper_trade(setup_id, 75, 100, 0)


def test_monitor_holds_and_records_event(tmp_path, monkeypatch):
    trade_id = _open_trade(tmp_path, monkeypatch)
    result = monitor_once(QuoteSource(110), now=datetime(2026, 8, 2, 14, 0))
    assert result["action"] == "HOLD"
    events = store.list_paper_monitor_events(trade_id)
    assert events[0]["action"] == "HOLD"


def test_monitor_target_one_moves_single_lot_to_breakeven(tmp_path, monkeypatch):
    trade_id = _open_trade(tmp_path, monkeypatch)
    result = monitor_once(QuoteSource(121), now=datetime(2026, 8, 2, 14, 0))
    assert result["action"] == "MANAGED"
    assert result["remaining_quantity"] == 75
    assert result["active_stop_loss"] >= 100
    assert store.get_open_paper_trade() is not None
    assert store.list_paper_monitor_events(trade_id)[0]["action"] == "MANAGED"


def test_monitor_forces_eod_exit(tmp_path, monkeypatch):
    _open_trade(tmp_path, monkeypatch)
    result = monitor_once(QuoteSource(105), now=datetime(2026, 8, 2, 15, 25))
    assert result["status"] == "CLOSED_EOD"
