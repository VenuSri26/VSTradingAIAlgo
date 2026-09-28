from types import SimpleNamespace

from app.decision_evidence import build_decision_evidence
from app.paper_costs import COST_MODEL_VERSION, option_trade_costs
from app.paper_decision_orchestrator import corroborate


def _preview(side="CE"):
    return {"status": "READY_FOR_HUMAN_REVIEW", "blockers": [], "candidate": {
        "option_type": side, "grade": "A", "alignment_score": 92, "rationale": []}}


def _decision(name="CE_BUY", grade="A", healthy="GREEN", risk=True):
    evidence = build_decision_evidence(
        {"timestamp": "2026-09-28T04:27:00+00:00", "finalized": True,
         "open": 100, "high": 110, "low": 95, "close": 105, "volume": 1000},
        {"decision": name},
    )
    return SimpleNamespace(
        decision=SimpleNamespace(decision=SimpleNamespace(value=name), grade=SimpleNamespace(value=grade),
                                 alignment_score=88, confidence=0.88, explanation="verified"),
        risk=SimpleNamespace(approved=risk),
        system_health=SimpleNamespace(overall=SimpleNamespace(value=healthy)),
        decision_evidence=evidence,
    )


def test_itemized_cost_model_is_deterministic_and_complete():
    result = option_trade_costs(100, 120, 65)
    assert result["model_version"] == COST_MODEL_VERSION
    assert result["total"] == round(sum(result[k] for k in (
        "brokerage", "stt", "exchange_charges", "sebi_charges", "stamp_duty", "gst")), 2)
    assert result["total"] > 0


def test_full_pipeline_corroborates_matching_a_grade_decision():
    result = corroborate(_preview(), _decision())
    assert result["status"] == "READY_FOR_HUMAN_REVIEW"
    assert result["candidate"]["alignment_score"] == 88
    assert result["full_pipeline"]["risk_approved"] is True


def test_full_pipeline_direction_conflict_fails_closed():
    result = corroborate(_preview("CE"), _decision("PE_BUY"))
    assert result["status"] == "BLOCKED"
    assert result["candidate"] is None
    assert any("DIRECTION_MISMATCH" in reason for reason in result["blockers"])


def test_full_pipeline_health_and_risk_veto_fail_closed():
    result = corroborate(_preview(), _decision(healthy="RED", risk=False))
    assert "FULL_PIPELINE_HEALTH_NOT_GREEN" in result["blockers"]
    assert "FULL_PIPELINE_RISK_VETO" in result["blockers"]
