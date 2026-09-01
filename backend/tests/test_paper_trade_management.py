from pathlib import Path

from app import store
from app.paper_trade_management import ensure_management, evaluate, get_management, close_manually


def _payload():
    return {
        "timestamp": "2026-08-05T09:30:00+00:00",
        "decision": {
            "decision": "CE_BUY", "grade": "A", "alignment_score": 85,
            "explanation": "test",
            "plan": {
                "option_type": "CE", "strike": 25000, "entry_low": 100,
                "entry_high": 105, "stop_loss": 90, "target_1": 120,
                "target_2": 140, "risk_reward": 2,
            },
        },
    }


def _open(tmp_path, monkeypatch, quantity=150):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "managed.db"))
    sid = store.create_trade_setup(f"managed-{quantity}", _payload())
    store.review_trade_setup(sid, "APPROVED", "ok")
    tid = store.open_paper_trade(sid, quantity, 100, 0)
    return store.get_open_paper_trade(), tid


def test_target_one_books_partial_and_moves_stop(tmp_path, monkeypatch):
    trade, tid = _open(tmp_path, monkeypatch, 150)
    result = evaluate(trade, 121)
    assert result["action"] == "MANAGED"
    assert "PARTIAL_EXIT_75" in result["actions"]
    assert result["remaining_quantity"] == 75
    assert result["active_stop_loss"] >= 100
    persisted = get_management(tid)
    assert persisted["partial_target_done"] == 1
    assert persisted["realized_quantity"] == 75


def test_trailing_stop_closes_remaining_with_aggregate_pnl(tmp_path, monkeypatch):
    trade, tid = _open(tmp_path, monkeypatch, 150)
    first = evaluate(trade, 125)
    assert first["remaining_quantity"] == 75
    raised = evaluate(trade, 135)
    assert raised["active_stop_loss"] >= 121.5
    closed = evaluate(trade, 121)
    assert closed["action"] == "CLOSED"
    assert closed["status"] == "CLOSED_TRAILING"
    assert closed["gross_pnl"] == (25 * 75) + (21 * 75)
    assert store.get_open_paper_trade() is None
    assert get_management(tid)["remaining_quantity"] == 0


def test_single_lot_moves_to_breakeven_without_partial(tmp_path, monkeypatch):
    trade, _ = _open(tmp_path, monkeypatch, 75)
    result = evaluate(trade, 121)
    assert result["remaining_quantity"] == 75
    assert "STOP_TO_BREAKEVEN" in result["actions"]
    assert not any(x.startswith("PARTIAL_EXIT") for x in result["actions"])


def test_manual_close_uses_partial_realized_pnl(tmp_path, monkeypatch):
    trade, _ = _open(tmp_path, monkeypatch, 150)
    evaluate(trade, 125)
    closed = close_manually(trade, 110, "USER_EXIT")
    assert closed is not None
    assert closed["gross_pnl"] == (25 * 75) + (10 * 75)
    assert closed["exit_reason"] == "USER_EXIT"
