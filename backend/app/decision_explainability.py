from __future__ import annotations

from dataclasses import asdict

from app.option_chain_intelligence import analyse_option_chain


def explain_decision(response, option_chain_snapshot: dict | None = None) -> dict:
    decision = response.decision.decision.value
    agents = [asdict(a) for a in response.agents]
    bullish = [a for a in agents if str(a.get("direction", "")).upper() in {"BULLISH", "BUY", "CE"}]
    bearish = [a for a in agents if str(a.get("direction", "")).upper() in {"BEARISH", "SELL", "PE"}]
    neutral = [a for a in agents if a not in bullish and a not in bearish]
    passed = []
    failed = []
    if response.risk.approved:
        passed.append("Risk supervisor approved the setup")
    else:
        failed.append("; ".join(response.risk.reasons) or "Risk supervisor blocked the setup")
    if response.alignment.score >= 70:
        passed.append(f"Agent alignment is strong at {response.alignment.score}/100")
    else:
        failed.append(f"Agent alignment is only {response.alignment.score}/100")
    if response.system_health.overall.value == "GREEN":
        passed.append("Market data freshness is healthy")
    else:
        failed.append("Market data is stale or degraded")

    option_intel = None
    if option_chain_snapshot:
        option_intel = analyse_option_chain(option_chain_snapshot)
        bias = option_intel.get("institutional_bias")
        if (decision == "CE_BUY" and bias == "BULLISH") or (decision == "PE_BUY" and bias == "BEARISH"):
            passed.append(f"Option-chain bias confirms the decision: {bias}")
        elif decision != "NO_TRADE" and bias not in {"NEUTRAL", None}:
            failed.append(f"Option-chain bias disagrees with the decision: {bias}")
        elif bias == "NEUTRAL":
            failed.append("Option-chain evidence is neutral")

    why = passed[:6]
    why_not = failed[:6]
    invalidations = []
    plan = getattr(response.decision, "plan", None)
    if plan:
        if getattr(plan, "stop_loss", None):
            invalidations.append(f"Option premium falls to stop-loss {plan.stop_loss}")
        if getattr(plan, "invalidation", None):
            invalidations.append(str(plan.invalidation))
    if not invalidations:
        invalidations.append("Risk supervisor changes the setup to blocked")
        invalidations.append("Market data becomes stale")

    return {
        "decision": decision,
        "grade": response.decision.grade.value,
        "confidence": response.decision.confidence or 0,
        "alignment_score": response.alignment.score or 0,
        "risk_approved": response.risk.approved,
        "checklist": {"passed": passed, "failed": failed},
        "why": why,
        "why_not": why_not,
        "invalidation_conditions": invalidations,
        "agent_votes": {"bullish": len(bullish), "bearish": len(bearish), "neutral": len(neutral)},
        "option_chain": option_intel,
        "summary": response.decision.explanation,
    }
