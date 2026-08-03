from __future__ import annotations
from app.models import AgentResult, AlignmentResult, TradeGrade, Direction
from app.agents.debate import EVIDENCE_FAMILIES

DEFAULT_WEIGHTS = {
    "Higher Timeframe Bias Agent": 0.15,
    "Regime Agent": 0.10,
    "Trend Agent": 0.15,
    "Momentum Agent": 0.10,
    "Liquidity Agent": 0.15,
    "Options/OI Agent": 0.15,
    "Gamma Agent": 0.05,
    "Trap Detection Agent": 0.05,
    "Risk Agent": 0.10,
}

DEFAULT_FAMILY_CAPS = {
    "TREND": 0.25, "MOMENTUM": 0.15, "REGIME": 0.15,
    "STRUCTURE": 0.20, "OPTIONS": 0.20, "RISK": 0.15, "OTHER": 0.10,
}

REGIME_MULTIPLIERS = {
    "TREND": {"TREND": 1.10, "MOMENTUM": 1.05, "REGIME": 1.0, "STRUCTURE": 1.0, "OPTIONS": 0.95, "RISK": 1.0},
    "RANGE": {"TREND": 0.85, "MOMENTUM": 0.90, "REGIME": 1.05, "STRUCTURE": 1.10, "OPTIONS": 1.05, "RISK": 1.0},
    "HIGH_VOLATILITY": {"TREND": 0.90, "MOMENTUM": 0.90, "REGIME": 1.10, "STRUCTURE": 1.05, "OPTIONS": 1.05, "RISK": 1.15},
}


def _effective_weights(agents, weights, family_caps, regime_label):
    mults = REGIME_MULTIPLIERS.get(regime_label, {})
    raw = {}
    for a in agents:
        family = EVIDENCE_FAMILIES.get(a.name, "OTHER")
        raw[a.name] = weights.get(a.name, 0.0) * mults.get(family, 1.0)
    # cap each correlated evidence family, preserving within-family proportions
    by_family = {}
    for name, value in raw.items():
        by_family.setdefault(EVIDENCE_FAMILIES.get(name, "OTHER"), []).append((name, value))
    effective = {}
    for family, items in by_family.items():
        total = sum(v for _, v in items)
        cap = family_caps.get(family, total)
        scale = min(1.0, cap / total) if total > 0 else 1.0
        for name, value in items:
            effective[name] = value * scale
    return effective


def compute_alignment(agents: list[AgentResult], weights: dict[str, float] | None = None,
                      family_caps: dict[str, float] | None = None,
                      regime_label: str | None = None) -> AlignmentResult:
    weights = weights or DEFAULT_WEIGHTS
    family_caps = family_caps or DEFAULT_FAMILY_CAPS
    available = [a for a in agents if a.score is not None]
    configured_total = sum(weights.values()) or 1.0
    available_weight = sum(weights.get(a.name, 0) for a in available)
    coverage_ratio = available_weight / configured_total
    if not available:
        return AlignmentResult(score=None, bullish_contribution=0, bearish_contribution=0,
            neutral_contribution=0, weights_used=weights, coverage_ratio=0.0,
            disagreement_score=0.0, calibrated_confidence=None, family_contributions={})

    effective = _effective_weights(available, weights, family_caps, regime_label)
    total_weight_used = sum(effective.values())
    if total_weight_used == 0:
        return AlignmentResult(score=None, bullish_contribution=0, bearish_contribution=0,
            neutral_contribution=0, weights_used=weights, coverage_ratio=coverage_ratio,
            disagreement_score=0.0, calibrated_confidence=None, family_contributions={})

    bull = bear = neutral = weighted_score = 0.0
    family_contributions: dict[str, float] = {}
    for a in available:
        normalized_w = effective.get(a.name, 0) / total_weight_used
        contribution = normalized_w * a.score
        weighted_score += contribution
        family = EVIDENCE_FAMILIES.get(a.name, "OTHER")
        family_contributions[family] = family_contributions.get(family, 0.0) + contribution
        if a.direction == Direction.BULLISH:
            bull += contribution
        elif a.direction == Direction.BEARISH:
            bear += contribution
        else:
            neutral += contribution

    directional = bull + bear
    disagreement = 0.0 if directional == 0 else 1.0 - abs(bull - bear) / directional
    raw_confidence = weighted_score / 100.0
    calibrated = raw_confidence * coverage_ratio * (1.0 - 0.50 * disagreement)
    return AlignmentResult(
        score=int(round(weighted_score)), bullish_contribution=round(bull, 1),
        bearish_contribution=round(bear, 1), neutral_contribution=round(neutral, 1),
        weights_used={k: round(v, 6) for k, v in effective.items()},
        coverage_ratio=round(coverage_ratio, 4), disagreement_score=round(disagreement, 4),
        calibrated_confidence=round(max(0.0, min(1.0, calibrated)), 4),
        family_contributions={k: round(v, 2) for k, v in family_contributions.items()},
    )


def classify_trade_grade(alignment: AlignmentResult, risk_approved: bool, dominant_direction: Direction,
                          conflicting_agents: int, min_coverage: float = 0.70,
                          max_disagreement: float = 0.45) -> TradeGrade:
    if not risk_approved or alignment.score is None:
        return TradeGrade.NO_TRADE
    if alignment.coverage_ratio < min_coverage or alignment.disagreement_score > max_disagreement:
        return TradeGrade.NO_TRADE
    score = alignment.score
    if conflicting_agents >= 3:
        return TradeGrade.NO_TRADE
    if score >= 85 and conflicting_agents == 0 and alignment.calibrated_confidence >= 0.65:
        return TradeGrade.A_PLUS
    if score >= 72 and conflicting_agents <= 1 and alignment.calibrated_confidence >= 0.50:
        return TradeGrade.A
    if score >= 55:
        return TradeGrade.B
    if score >= 40:
        return TradeGrade.C
    return TradeGrade.NO_TRADE
