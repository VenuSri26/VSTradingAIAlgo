from app.production_candidate import production_candidate_status


def test_production_candidate_is_safety_gated():
    result = production_candidate_status()
    assert result["execution_mode"] == "PAPER_ONLY"
    assert result["live_orders_enabled"] is False
    assert 0 <= result["readiness_score"] <= 100
    assert result["rules"]


def test_readiness_has_evidence_gates():
    result = production_candidate_status()
    codes = {row["code"] for row in result["rules"]}
    assert {"PAPER_SAMPLE", "PROFIT_FACTOR", "DRAWDOWN", "LIVE_DISABLED"}.issubset(codes)
