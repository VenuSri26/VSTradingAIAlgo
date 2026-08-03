from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import store


def _payload(signature: str, grade: str = "A", option_type: str = "CE"):
    return {
        "timestamp": "2026-08-03T04:00:00+00:00",
        "market": {"nifty_spot": 25000, "vix": 13.2},
        "decision": {
            "decision": f"{option_type}_BUY", "grade": grade, "alignment_score": 80,
            "explanation": f"{signature} evidence", "plan": {
                "option_type": option_type, "strike": 25000, "entry_low": 100,
                "entry_high": 105, "stop_loss": 90, "target_1": 120,
                "target_2": 140, "risk_reward": 2,
            },
        },
    }


def _closed_trade(signature, pnl_price, tmp_path, monkeypatch, grade="A", option_type="CE"):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "analytics.db"))
    setup_id = store.create_trade_setup(signature, _payload(signature, grade, option_type))
    store.review_trade_setup(setup_id, "APPROVED", "analytics test")
    trade_id = store.open_paper_trade(setup_id, 75, 100)
    return trade_id, store.close_paper_trade(trade_id, pnl_price, "CLOSED_MANUAL", 10, "MANUAL")


def test_paper_analytics_and_equity_curve(tmp_path, monkeypatch):
    _closed_trade("win", 120, tmp_path, monkeypatch, "A+", "CE")
    _closed_trade("loss", 90, tmp_path, monkeypatch, "B", "PE")
    result = store.paper_analytics_summary()
    assert result["summary"]["total_trades"] == 2
    assert result["summary"]["wins"] == 1
    assert result["summary"]["losses"] == 1
    assert result["summary"]["net_pnl"] == 730.0
    assert len(result["equity_curve"]) == 2
    assert result["by_option_type"]["CE"]["trades"] == 1
    assert result["by_option_type"]["PE"]["trades"] == 1
    assert result["summary"]["max_drawdown"] == 760.0


def test_decision_replay_includes_snapshot_and_events(tmp_path, monkeypatch):
    trade_id, _ = _closed_trade("replay", 115, tmp_path, monkeypatch)
    store.record_paper_monitor_event(trade_id, 108, "HOLD", "monitoring")
    replay = store.get_decision_replay(trade_id)
    assert replay["trade"]["id"] == trade_id
    assert replay["setup"]["grade"] == "A"
    assert replay["market_snapshot"]["market"]["nifty_spot"] == 25000
    assert replay["events"][0]["action"] == "HOLD"
    assert replay["execution_mode"] == "PAPER_ONLY"
