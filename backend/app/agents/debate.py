"""Deterministic multi-agent debate and confidence diagnostics.

This module does not call an LLM and cannot place orders. It summarizes the
existing agent evidence into bull/bear cases and computes disagreement and
coverage diagnostics used as conservative gates in the decision pipeline.
"""
from __future__ import annotations
from dataclasses import dataclass
from app.models import AgentResult, Direction

EVIDENCE_FAMILIES = {
    "Higher Timeframe Bias Agent": "TREND",
    "Trend Agent": "TREND",
    "Momentum Agent": "MOMENTUM",
    "Regime Agent": "REGIME",
    "Liquidity Agent": "STRUCTURE",
    "Trap Detection Agent": "STRUCTURE",
    "Options/OI Agent": "OPTIONS",
    "Gamma Agent": "OPTIONS",
    "Risk Agent": "RISK",
}

@dataclass
class DebateResult:
    bull_case: list[str]
    bear_case: list[str]
    neutral_case: list[str]
    bullish_weight: float
    bearish_weight: float
    disagreement_score: float
    available_weight: float
    coverage_ratio: float
    dominant_direction: Direction
    conflicting_agents: int
    family_directions: dict[str, str]


def build_debate(agents: list[AgentResult], weights: dict[str, float]) -> DebateResult:
    available = [a for a in agents if a.score is not None]
    available_weight = sum(weights.get(a.name, 0.0) for a in available)
    total_weight = sum(weights.values()) or 1.0
    coverage = min(1.0, available_weight / total_weight)

    bull = sum(weights.get(a.name, 0.0) for a in available if a.direction == Direction.BULLISH)
    bear = sum(weights.get(a.name, 0.0) for a in available if a.direction == Direction.BEARISH)
    directional_total = bull + bear
    disagreement = 0.0 if directional_total == 0 else 1.0 - abs(bull - bear) / directional_total
    dominant = Direction.BULLISH if bull > bear else Direction.BEARISH if bear > bull else Direction.NEUTRAL
    conflicting = sum(1 for a in available if a.direction in (Direction.BULLISH, Direction.BEARISH) and a.direction != dominant)

    cases = {Direction.BULLISH: [], Direction.BEARISH: [], Direction.NEUTRAL: []}
    family_votes: dict[str, dict[Direction, float]] = {}
    for a in available:
        family = EVIDENCE_FAMILIES.get(a.name, "OTHER")
        family_votes.setdefault(family, {Direction.BULLISH: 0.0, Direction.BEARISH: 0.0, Direction.NEUTRAL: 0.0})
        direction = a.direction if a.direction in cases else Direction.NEUTRAL
        family_votes[family][direction] += weights.get(a.name, 0.0)
        evidence = a.evidence[0] if a.evidence else a.reason
        cases[direction].append(f"{a.name}: {evidence}")

    family_directions: dict[str, str] = {}
    for family, votes in family_votes.items():
        if votes[Direction.BULLISH] > votes[Direction.BEARISH]:
            family_directions[family] = Direction.BULLISH.value
        elif votes[Direction.BEARISH] > votes[Direction.BULLISH]:
            family_directions[family] = Direction.BEARISH.value
        else:
            family_directions[family] = Direction.NEUTRAL.value

    return DebateResult(
        bull_case=cases[Direction.BULLISH], bear_case=cases[Direction.BEARISH],
        neutral_case=cases[Direction.NEUTRAL], bullish_weight=round(bull, 4),
        bearish_weight=round(bear, 4), disagreement_score=round(disagreement, 4),
        available_weight=round(available_weight, 4), coverage_ratio=round(coverage, 4),
        dominant_direction=dominant, conflicting_agents=conflicting,
        family_directions=family_directions,
    )
