from app.data_sources.mock_source import MockDataSource
from app.option_chain_intelligence import analyse_option_chain, calculate_max_pain


def test_option_chain_summary_has_core_metrics():
    snapshot = MockDataSource(seed=7).get_option_chain(atm_range=5)
    summary = analyse_option_chain(snapshot)
    assert summary["atm_strike"] > 0
    assert summary["total_ce_oi"] > 0
    assert summary["total_pe_oi"] > 0
    assert summary["pcr_oi"] is not None
    assert summary["call_wall"] is not None
    assert summary["put_wall"] is not None
    assert summary["max_pain"] is not None
    assert summary["institutional_bias"] in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert 0 <= summary["bias_score"] <= 100


def test_max_pain_prefers_middle_strike_for_symmetric_chain():
    ce = [{"strike": 100, "oi": 100}, {"strike": 110, "oi": 100}, {"strike": 120, "oi": 100}]
    pe = [{"strike": 100, "oi": 100}, {"strike": 110, "oi": 100}, {"strike": 120, "oi": 100}]
    assert calculate_max_pain(ce, pe) == 110


def test_incomplete_chain_is_safe_and_warns():
    summary = analyse_option_chain({"spot": 25000, "atm": 25000, "chain": {"CE": [], "PE": []}})
    assert summary["institutional_bias"] == "NEUTRAL"
    assert summary["confidence"] <= 40
    assert summary["warnings"]
