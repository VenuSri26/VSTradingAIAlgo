from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import store
from app.risk_supervisor import evaluate_paper_entry, status
from app.config import settings


def _payload():
    return {"timestamp":"2026-08-02T10:00:00+00:00","decision":{"decision":"CE_BUY","grade":"A","alignment_score":80,"explanation":"x","plan":{"option_type":"CE","strike":25000,"entry_low":100,"entry_high":105,"stop_loss":90,"target_1":120,"target_2":140,"risk_reward":2}}}


def test_risk_supervisor_allows_safe_trade(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "risk.db"))
    monkeypatch.setattr(settings, "max_risk_per_trade_pct", 10.0)
    setup_id = store.create_trade_setup("risk-safe", _payload())
    setup = store.review_trade_setup(setup_id, "APPROVED", "ok")
    decision = evaluate_paper_entry(setup, 100)
    assert decision.approved is True
    assert decision.max_quantity >= settings.nifty_lot_size


def test_kill_switch_blocks_trade(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "risk-kill.db"))
    setup_id = store.create_trade_setup("risk-kill", _payload())
    setup = store.review_trade_setup(setup_id, "APPROVED", "ok")
    store.set_kill_switch(True, "manual stop")
    decision = evaluate_paper_entry(setup, 100)
    assert decision.approved is False
    assert any("kill switch" in reason.lower() for reason in decision.reasons)
    assert status()["kill_switch"] is True


def test_portfolio_summary_and_timeline(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "portfolio.db"))
    setup_id = store.create_trade_setup("risk-summary", _payload())
    store.review_trade_setup(setup_id, "APPROVED", "ok")
    trade_id = store.open_paper_trade(setup_id, 75, 100, 0)
    store.record_paper_monitor_event(trade_id, 110, "HOLD", "tracking")
    store.close_paper_trade(trade_id, 120, "CLOSED_TARGET_1", 20, "TARGET_1")
    summary = store.paper_portfolio_summary()
    assert summary["closed_trades"] == 1
    assert summary["wins"] == 1
    timeline = store.get_trade_timeline(trade_id)
    assert timeline["trade"]["id"] == trade_id
    assert timeline["events"][0]["action"] == "HOLD"
