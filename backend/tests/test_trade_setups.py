import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import store


def test_trade_setup_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "test.db"))
    payload = {
        "timestamp": "2026-08-02T10:00:00+00:00",
        "decision": {
            "decision": "CE_BUY", "grade": "A", "alignment_score": 77,
            "explanation": "test", "plan": {
                "option_type": "CE", "strike": 25000, "entry_low": 100,
                "entry_high": 105, "stop_loss": 85, "target_1": 125,
                "target_2": 145, "risk_reward": 1.67,
            },
        },
    }
    setup_id = store.create_trade_setup("sig-1", payload)
    assert setup_id is not None
    assert store.create_trade_setup("sig-1", payload) is None
    rows = store.list_trade_setups(status="GENERATED")
    assert len(rows) == 1
    reviewed = store.review_trade_setup(setup_id, "APPROVED", "paper trade")
    assert reviewed["status"] == "APPROVED"
    assert store.list_trade_setups(status="APPROVED")[0]["id"] == setup_id
