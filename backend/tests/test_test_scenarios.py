from app.test_scenarios import ScenarioInput, evaluate_scenario, run_release_scenarios


def test_release_scenario_suite_passes():
    result = run_release_scenarios()
    assert result["status"] == "PASS"
    assert result["passed"] == result["total"] == 10
    assert result["failed"] == 0
    assert result["live_orders_enabled"] is False


def test_risk_veto_is_absolute():
    scenario = ScenarioInput(
        name="risk", description="", dominant_direction="BULLISH",
        alignment_score=100, confidence=1.0, risk_approved=False,
        data_fresh=True, htf_aligned=True, vwap_aligned=True,
        ema_aligned=True, momentum_confirmed=True, options_supportive=True,
        no_trap=True, risk_reward=5.0, market_open=True,
    )
    decision, grade, blockers = evaluate_scenario(scenario)
    assert decision == "NO_TRADE"
    assert grade == "REJECT"
    assert "risk supervisor veto" in blockers


def test_valid_bearish_scenario_produces_pe_buy():
    scenario = ScenarioInput(
        name="bear", description="", dominant_direction="BEARISH",
        alignment_score=80, confidence=0.75, risk_approved=True,
        data_fresh=True, htf_aligned=True, vwap_aligned=True,
        ema_aligned=True, momentum_confirmed=True, options_supportive=True,
        no_trap=True, risk_reward=1.8, market_open=True,
    )
    decision, grade, blockers = evaluate_scenario(scenario)
    assert decision == "PE_BUY"
    assert grade == "A"
    assert blockers == []
