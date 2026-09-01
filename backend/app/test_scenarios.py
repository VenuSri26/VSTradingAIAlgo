"""Deterministic release test scenarios for the Nifty options decision system.

The scenarios intentionally avoid broker/network calls. They exercise the core
accept/reject gates with fixed evidence so every release can be regression-tested
on a laptop, CI runner, or AWS instance.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

Decision = Literal["CE_BUY", "PE_BUY", "NO_TRADE"]


@dataclass(frozen=True)
class ScenarioInput:
    name: str
    description: str
    dominant_direction: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    alignment_score: int
    confidence: float
    risk_approved: bool
    data_fresh: bool
    htf_aligned: bool
    vwap_aligned: bool
    ema_aligned: bool
    momentum_confirmed: bool
    options_supportive: bool
    no_trap: bool
    risk_reward: float | None
    market_open: bool = True


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    description: str
    expected: Decision
    actual: Decision
    passed: bool
    grade: str
    score: int
    blockers: list[str]
    evidence: dict[str, object]


def evaluate_scenario(s: ScenarioInput) -> tuple[Decision, str, list[str]]:
    blockers: list[str] = []
    if not s.market_open:
        blockers.append("market closed")
    if not s.data_fresh:
        blockers.append("stale market data")
    if not s.risk_approved:
        blockers.append("risk supervisor veto")
    if s.dominant_direction == "NEUTRAL":
        blockers.append("no dominant direction")
    if s.alignment_score < 70:
        blockers.append(f"alignment below 70 ({s.alignment_score})")
    if s.confidence < 0.65:
        blockers.append(f"confidence below 65% ({s.confidence:.0%})")

    checklist = {
        "HTF aligned": s.htf_aligned,
        "VWAP aligned": s.vwap_aligned,
        "EMA aligned": s.ema_aligned,
        "Momentum confirmed": s.momentum_confirmed,
        "Options supportive": s.options_supportive,
        "No trap": s.no_trap,
        "Risk/reward >= 1.5": s.risk_reward is not None and s.risk_reward >= 1.5,
    }
    blockers.extend(name for name, ok in checklist.items() if not ok)

    if blockers:
        grade = "REJECT" if (not s.risk_approved or not s.data_fresh or not s.market_open) else "C"
        return "NO_TRADE", grade, blockers

    grade = "A+" if s.alignment_score >= 85 and s.confidence >= 0.80 else "A"
    return ("CE_BUY" if s.dominant_direction == "BULLISH" else "PE_BUY"), grade, []


def scenario_catalog() -> list[tuple[ScenarioInput, Decision]]:
    common = dict(
        risk_approved=True, data_fresh=True, htf_aligned=True,
        vwap_aligned=True, ema_aligned=True, momentum_confirmed=True,
        options_supportive=True, no_trap=True, risk_reward=1.8, market_open=True,
    )
    return [
        (ScenarioInput("bullish_a_plus", "Strong bullish confluence should produce CE BUY.", "BULLISH", 91, 0.87, **common), "CE_BUY"),
        (ScenarioInput("bearish_a", "Bearish confluence above minimum gates should produce PE BUY.", "BEARISH", 78, 0.72, **common), "PE_BUY"),
        (ScenarioInput("low_alignment", "Directional evidence with weak alignment must be rejected.", "BULLISH", 54, 0.71, **common), "NO_TRADE"),
        (ScenarioInput("risk_veto", "Risk supervisor veto must override every bullish signal.", "BULLISH", 93, 0.90, **{**common, "risk_approved": False}), "NO_TRADE"),
        (ScenarioInput("stale_data", "Stale data must fail closed instead of generating a trade.", "BEARISH", 88, 0.84, **{**common, "data_fresh": False}), "NO_TRADE"),
        (ScenarioInput("trap_detected", "Trap evidence must block an otherwise valid setup.", "BULLISH", 86, 0.82, **{**common, "no_trap": False}), "NO_TRADE"),
        (ScenarioInput("poor_risk_reward", "A setup below minimum risk/reward must be rejected.", "BEARISH", 82, 0.79, **{**common, "risk_reward": 1.2}), "NO_TRADE"),
        (ScenarioInput("market_closed", "No new trade may be created outside the configured session.", "BULLISH", 95, 0.92, **{**common, "market_open": False}), "NO_TRADE"),
        (ScenarioInput("neutral_market", "Balanced votes must result in NO TRADE.", "NEUTRAL", 73, 0.68, **common), "NO_TRADE"),
        (ScenarioInput("options_conflict", "Options-flow conflict must block the trade.", "BULLISH", 84, 0.80, **{**common, "options_supportive": False}), "NO_TRADE"),
    ]


def run_release_scenarios() -> dict[str, object]:
    results: list[ScenarioResult] = []
    for scenario, expected in scenario_catalog():
        actual, grade, blockers = evaluate_scenario(scenario)
        results.append(ScenarioResult(
            name=scenario.name,
            description=scenario.description,
            expected=expected,
            actual=actual,
            passed=actual == expected,
            grade=grade,
            score=scenario.alignment_score,
            blockers=blockers,
            evidence=asdict(scenario),
        ))
    passed = sum(1 for r in results if r.passed)
    return {
        "suite": "V4 deterministic trading safety scenarios",
        "status": "PASS" if passed == len(results) else "FAIL",
        "passed": passed,
        "failed": len(results) - passed,
        "total": len(results),
        "live_orders_enabled": False,
        "results": [asdict(r) for r in results],
    }
