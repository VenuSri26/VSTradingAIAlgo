from __future__ import annotations
from typing import Any


def _direction_score(direction: str | None) -> float:
    return 100.0 if direction == "BULLISH" else 0.0 if direction == "BEARISH" else 50.0


def build_supervisor_decision(base_response: Any, regime: dict[str, Any], structure: dict[str, Any], gamma: dict[str, Any], institutional: dict[str, Any] | None) -> dict[str, Any]:
    trend_score = float(regime.get("trend_score", 50.0))
    structure_score = float(structure.get("structure_score", 50.0))
    institutional_score = 50.0
    if institutional:
        flow = float(institutional.get("institutional_flow_score", 0.0))
        institutional_score = max(0.0, min(100.0, 50.0 + flow / 2.0))
    gamma_score = 60.0 if gamma.get("dealer_regime") == "LONG_GAMMA" else 40.0 if gamma.get("dealer_regime") == "SHORT_GAMMA" else 50.0
    risk_score = 90.0 if bool(base_response.risk.approved) else 15.0

    weights = {"trend": 0.24, "institutional": 0.24, "structure": 0.22, "gamma": 0.12, "risk": 0.18}
    overall = sum(score * weights[name] for name, score in {
        "trend": trend_score, "institutional": institutional_score,
        "structure": structure_score, "gamma": gamma_score, "risk": risk_score,
    }.items())

    bullish_votes = sum(s >= 58 for s in (trend_score, institutional_score, structure_score, gamma_score))
    bearish_votes = sum(s <= 42 for s in (trend_score, institutional_score, structure_score, gamma_score))
    direction = "CE_BUY" if bullish_votes >= 3 and risk_score >= 60 else "PE_BUY" if bearish_votes >= 3 and risk_score >= 60 else "NO_TRADE"
    if overall >= 88 and direction != "NO_TRADE": grade = "A+"
    elif overall >= 78 and direction != "NO_TRADE": grade = "A"
    elif overall >= 65 and direction != "NO_TRADE": grade = "B"
    elif overall >= 55: grade = "C"
    else: grade = "REJECT"
    if grade not in {"A+", "A"}:
        direction = "NO_TRADE"

    reasons = []
    blockers = []
    for label, score in (("Trend", trend_score), ("Institutional", institutional_score), ("Structure", structure_score), ("Gamma", gamma_score), ("Risk", risk_score)):
        (reasons if score >= 58 else blockers if score <= 42 else reasons).append(f"{label} score {score:.1f}")
    invalidations = []
    if structure.get("range"):
        invalidations.append(f"Structure breaks below {structure['range']['low']:.2f} or above {structure['range']['high']:.2f} against the selected side")
    if gamma.get("gamma_flip"):
        invalidations.append(f"Dealer regime changes around gamma flip {gamma['gamma_flip']}")
    invalidations.append("Risk supervisor blocks the setup or market data becomes stale")

    return {
        "decision": direction, "grade": grade,
        "overall_score": round(overall, 2), "confidence": round(overall, 2),
        "scores": {"trend": round(trend_score,2), "institutional": round(institutional_score,2), "structure": round(structure_score,2), "gamma": round(gamma_score,2), "risk": round(risk_score,2)},
        "weights": weights,
        "votes": {"bullish": bullish_votes, "bearish": bearish_votes, "neutral": 4 - bullish_votes - bearish_votes},
        "market_regime": regime,
        "structure": structure,
        "gamma": gamma,
        "institutional_flow": institutional,
        "why": reasons,
        "why_not": blockers,
        "invalidation_conditions": invalidations,
        "execution_mode": "DECISION_SUPPORT_PAPER_ONLY",
        "live_orders_enabled": False,
    }
