from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import store


def _payload():
    return {"timestamp":"2026-08-02T10:00:00+00:00","decision":{"decision":"CE_BUY","grade":"A","alignment_score":80,"explanation":"x","plan":{"option_type":"CE","strike":25000,"entry_low":100,"entry_high":105,"stop_loss":90,"target_1":120,"target_2":140,"risk_reward":2}}}

def test_paper_trade_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "paper.db"))
    setup_id=store.create_trade_setup("paper-1", _payload())
    store.review_trade_setup(setup_id, "APPROVED", "ok")
    trade_id=store.open_paper_trade(setup_id, 75, 100, 0.5)
    trade=store.get_open_paper_trade()
    assert trade["id"] == trade_id
    assert trade["entry_price"] == 100.5
    closed=store.close_paper_trade(trade_id, 120, "CLOSED_TARGET_1", 25, "TARGET_1")
    assert closed["gross_pnl"] == 1462.5
    assert closed["net_pnl"] == 1437.5
    assert store.get_open_paper_trade() is None
