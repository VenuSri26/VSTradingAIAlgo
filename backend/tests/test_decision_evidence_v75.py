import copy

import pytest

from app.decision_evidence import build_decision_evidence, verify_decision_evidence


def _candle(**overrides):
    candle = {
        "timestamp": "2026-09-16T09:18:00+05:30", "finalized": True,
        "open": 25000, "high": 25020, "low": 24990, "close": 25010,
        "volume": 1200, "ticks": 180,
    }
    candle.update(overrides)
    return candle


def test_evidence_is_deterministic_and_verifiable():
    first = build_decision_evidence(_candle(), {"decision": "CE_BUY", "score": 82})
    second = build_decision_evidence(_candle(), {"score": 82, "decision": "CE_BUY"})
    assert first == second
    assert verify_decision_evidence(first) is True


def test_changed_bar_or_feature_invalidates_certificate():
    evidence = build_decision_evidence(_candle(), {"decision": "CE_BUY", "score": 82})
    tampered = copy.deepcopy(evidence)
    tampered["bar"]["close"] = 25011
    assert verify_decision_evidence(tampered) is False
    tampered = copy.deepcopy(evidence)
    tampered["feature_hash"] = "0" * 64
    assert verify_decision_evidence(tampered) is False


def test_forming_or_misaligned_bar_cannot_be_certified():
    with pytest.raises(ValueError, match="finalized"):
        build_decision_evidence(_candle(finalized=False), {})
    with pytest.raises(ValueError, match="exchange-aligned"):
        build_decision_evidence(_candle(timestamp="2026-09-16T09:19:00+05:30"), {})


def test_timezone_is_mandatory():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_decision_evidence(_candle(timestamp="2026-09-16T09:18:00"), {})
