from app.operations import system_snapshot
from app.strategy_lab import sample_payload, validate_strategy


def test_operations_snapshot_has_resources():
    snap = system_snapshot()
    assert snap["version"]
    assert "memory" in snap and "disk" in snap
    assert snap["trading_mode"] in {"mock", "live"}


def test_strategy_lab_sample_runs_conservatively():
    result = validate_strategy(sample_payload())
    assert result["promotion_status"] == "RESEARCH_ONLY"
    assert result["summary"]["total"] >= 1
    assert result["walk_forward_splits"]


def test_strategy_lab_rejects_missing_candles():
    try:
        validate_strategy({"candles": [], "signals": []})
    except ValueError as exc:
        assert "two candles" in str(exc)
    else:
        raise AssertionError("Expected validation error")
