from __future__ import annotations

from dataclasses import asdict

AGENT_FAMILIES = {
    "Higher Timeframe Bias Agent": "TREND",
    "Regime Agent": "REGIME",
    "Trend Agent": "TREND",
    "Momentum Agent": "MOMENTUM",
    "Liquidity Agent": "STRUCTURE",
    "Options/OI Agent": "OPTIONS",
    "Gamma Agent": "OPTIONS",
    "Trap Detection Agent": "STRUCTURE",
    "Risk Agent": "RISK",
}

AGENT_PURPOSES = {
    "Higher Timeframe Bias Agent": "Confirms directional agreement across higher timeframes.",
    "Regime Agent": "Classifies trend, range and volatility conditions.",
    "Trend Agent": "Measures EMA and VWAP directional structure.",
    "Momentum Agent": "Measures momentum and relative-volume confirmation.",
    "Liquidity Agent": "Maps nearby liquidity and structural price levels.",
    "Options/OI Agent": "Evaluates option-chain open-interest evidence.",
    "Gamma Agent": "Evaluates gamma walls, pinning and exposure evidence.",
    "Trap Detection Agent": "Detects possible breakout and directional traps.",
    "Risk Agent": "Applies session, freshness, volatility and reward/risk vetoes.",
}


def registry_snapshot(response) -> dict:
    agents = []
    for agent in response.agents:
        item = asdict(agent)
        item["direction"] = agent.direction.value
        item["availability"] = agent.availability.value
        item["family"] = AGENT_FAMILIES.get(agent.name, "OTHER")
        item["purpose"] = AGENT_PURPOSES.get(agent.name, "Decision-support evidence agent.")
        agents.append(item)
    return {
        "agents": agents,
        "alignment": asdict(response.alignment),
        "debate": response.debate,
        "final_decision": asdict(response.decision),
        "execution_mode": "DECISION_SUPPORT_PAPER_ONLY",
    }
