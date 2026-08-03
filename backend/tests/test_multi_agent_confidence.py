from app.agents.alignment import compute_alignment, classify_trade_grade, DEFAULT_WEIGHTS
from app.agents.debate import build_debate
from app.models import AgentResult, Direction, TradeGrade


def agent(name, score, direction):
    return AgentResult(name=name, score=score, direction=direction, confidence=0.8,
        reason="test", evidence=["evidence"], weight=DEFAULT_WEIGHTS[name])


def test_debate_detects_balanced_disagreement():
    agents = [agent("Trend Agent", 80, Direction.BULLISH), agent("Options/OI Agent", 80, Direction.BEARISH)]
    result = build_debate(agents, DEFAULT_WEIGHTS)
    assert result.disagreement_score == 1.0
    assert result.dominant_direction == Direction.NEUTRAL


def test_alignment_reports_coverage():
    agents = [agent("Trend Agent", 80, Direction.BULLISH)]
    result = compute_alignment(agents, DEFAULT_WEIGHTS)
    assert result.coverage_ratio == 0.15
    assert result.calibrated_confidence is not None


def test_low_coverage_blocks_grade_a():
    agents = [agent("Trend Agent", 95, Direction.BULLISH)]
    alignment = compute_alignment(agents, DEFAULT_WEIGHTS)
    grade = classify_trade_grade(alignment, True, Direction.BULLISH, 0)
    assert grade == TradeGrade.NO_TRADE


def test_high_disagreement_blocks_trade():
    agents = [
        agent("Higher Timeframe Bias Agent", 90, Direction.BULLISH),
        agent("Trend Agent", 90, Direction.BULLISH),
        agent("Options/OI Agent", 90, Direction.BEARISH),
        agent("Liquidity Agent", 90, Direction.BEARISH),
        agent("Regime Agent", 80, Direction.NEUTRAL),
        agent("Momentum Agent", 80, Direction.NEUTRAL),
        agent("Risk Agent", 100, Direction.NEUTRAL),
    ]
    alignment = compute_alignment(agents, DEFAULT_WEIGHTS)
    assert alignment.disagreement_score > 0.45
    assert classify_trade_grade(alignment, True, Direction.BULLISH, 2) == TradeGrade.NO_TRADE


def test_family_caps_limit_correlated_trend_weight():
    agents = [
        agent("Higher Timeframe Bias Agent", 100, Direction.BULLISH),
        agent("Trend Agent", 100, Direction.BULLISH),
        agent("Momentum Agent", 50, Direction.NEUTRAL),
        agent("Regime Agent", 50, Direction.NEUTRAL),
        agent("Liquidity Agent", 50, Direction.NEUTRAL),
        agent("Options/OI Agent", 50, Direction.NEUTRAL),
        agent("Gamma Agent", 50, Direction.NEUTRAL),
        agent("Trap Detection Agent", 50, Direction.NEUTRAL),
        agent("Risk Agent", 100, Direction.NEUTRAL),
    ]
    alignment = compute_alignment(agents, DEFAULT_WEIGHTS)
    assert alignment.weights_used["Higher Timeframe Bias Agent"] + alignment.weights_used["Trend Agent"] <= 0.250001
