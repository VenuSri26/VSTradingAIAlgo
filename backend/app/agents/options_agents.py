from __future__ import annotations
from app.models import AgentResult, Direction, Availability, utcnow
from .base import clamp, direction_from_score, to_public_score, not_available


def _chain_totals(chain: dict) -> dict:
    ce = chain.get("CE", [])
    pe = chain.get("PE", [])
    ce_oi = sum(x["oi"] for x in ce if x.get("oi") is not None)
    pe_oi = sum(x["oi"] for x in pe if x.get("oi") is not None)
    ce_oi_chg = sum(x["oi_change"] for x in ce if x.get("oi_change") is not None)
    pe_oi_chg = sum(x["oi_change"] for x in pe if x.get("oi_change") is not None)
    call_wall = max(ce, key=lambda x: x.get("oi") or 0, default=None)
    put_wall = max(pe, key=lambda x: x.get("oi") or 0, default=None)
    return dict(ce_oi=ce_oi, pe_oi=pe_oi, ce_oi_chg=ce_oi_chg, pe_oi_chg=pe_oi_chg,
                call_wall=call_wall, put_wall=put_wall)


def options_oi_agent(option_snapshot: dict, weight: float) -> tuple[AgentResult, dict]:
    """Returns (AgentResult, computed_metrics) — metrics reused by the
    options-intelligence panel and gamma agent so numbers stay consistent."""
    chain = option_snapshot.get("chain")
    if not chain or not (chain.get("CE") or chain.get("PE")):
        return not_available("Options/OI Agent", weight, "Option chain unavailable"), {}

    totals = _chain_totals(chain)
    pcr = round(totals["pe_oi"] / totals["ce_oi"], 2) if totals["ce_oi"] else None
    evidence = []
    if pcr is not None:
        evidence.append(f"PCR: {pcr}")
    if totals["ce_oi_chg"] and totals["pe_oi_chg"]:
        if totals["ce_oi_chg"] > 0 and totals["ce_oi_chg"] > totals["pe_oi_chg"]:
            evidence.append("Fresh CE OI buildup dominant — resistance being defended")
        elif totals["pe_oi_chg"] > 0 and totals["pe_oi_chg"] > totals["ce_oi_chg"]:
            evidence.append("Fresh PE OI buildup dominant — support being defended")
        if totals["ce_oi_chg"] < 0:
            evidence.append("CE unwinding observed")
        if totals["pe_oi_chg"] < 0:
            evidence.append("PE unwinding observed")

    signed = 0.0
    if pcr is not None:
        # PCR > 1.2 skews bullish (heavy put writing = support), < 0.8 bearish
        signed += clamp((pcr - 1.0) * 80, -50, 50)
    if totals["ce_oi_chg"] is not None and totals["pe_oi_chg"] is not None:
        net_chg = totals["pe_oi_chg"] - totals["ce_oi_chg"]
        signed += clamp(net_chg / 50000, -40, 40)

    signed = clamp(signed, -100, 100)
    direction = direction_from_score(signed)
    sentiment_score = to_public_score(signed)

    if totals["call_wall"]:
        evidence.append(f"Call wall: {totals['call_wall']['strike']} (OI {totals['call_wall']['oi']:,})")
    if totals["put_wall"]:
        evidence.append(f"Put wall: {totals['put_wall']['strike']} (OI {totals['put_wall']['oi']:,})")

    result = AgentResult(
        name="Options/OI Agent", score=sentiment_score, direction=direction,
        confidence=round(abs(signed) / 100, 2), weight=weight,
        reason=f"Options positioning reads {direction.value.lower()} (PCR {pcr}).",
        evidence=evidence, timestamp=utcnow(),
    )
    metrics = dict(pcr=pcr, sentiment_score=sentiment_score, **totals)
    return result, metrics


def _compute_net_gex(chain: dict, spot: float, contract_multiplier: int = 75) -> float | None:
    """Net Gamma Exposure: sum(call gamma * call OI) - sum(put gamma * put
    OI), scaled by contract size and spot. This is the standard retail GEX
    approximation (dealer short-gamma-on-puts / long-gamma-on-calls
    convention — real market-maker positioning can differ from this
    assumption, so treat the SIGN as a directional signal, not a certainty).
    Requires the chain to already be Greeks-enriched (see app/greeks.py);
    returns None rather than a guess if gamma data isn't present."""
    ce_gex = sum(
        (leg.get("gamma") or 0) * (leg.get("oi") or 0)
        for leg in chain.get("CE", []) if leg.get("gamma") is not None
    )
    pe_gex = sum(
        (leg.get("gamma") or 0) * (leg.get("oi") or 0)
        for leg in chain.get("PE", []) if leg.get("gamma") is not None
    )
    if ce_gex == 0 and pe_gex == 0:
        return None
    net = (ce_gex - pe_gex) * contract_multiplier * spot
    return round(net, 0)


def gamma_agent(option_snapshot: dict, oi_metrics: dict, spot: float, weight: float) -> tuple[AgentResult, dict]:
    call_wall = oi_metrics.get("call_wall")
    put_wall = oi_metrics.get("put_wall")
    if not call_wall or not put_wall:
        return not_available("Gamma Agent", weight, "Insufficient option OI data for gamma estimate"), {}

    cw_strike, pw_strike = call_wall["strike"], put_wall["strike"]
    gamma_flip = round((cw_strike + pw_strike) / 2, 1)
    evidence = [f"Call wall: {cw_strike}", f"Put wall: {pw_strike}", f"Gamma flip (est.): {gamma_flip}"]

    net_gex = _compute_net_gex(option_snapshot.get("chain", {}), spot)
    if net_gex is not None:
        gex_label = "positive (dampening)" if net_gex > 0 else "negative (accelerating)"
        evidence.append(f"Net GEX: {net_gex:,.0f} ({gex_label})")

    pinning = abs(spot - gamma_flip) / spot < 0.003
    if pinning:
        evidence.append("Spot sitting near midpoint of call/put walls — pinning risk")

    if spot >= cw_strike:
        signed, regime = 40, "above call wall — potential gamma squeeze zone"
        expected_vol = "Expansion likely if call wall breaks with volume"
    elif spot <= pw_strike:
        signed, regime = -40, "below put wall — downside gamma acceleration risk"
        expected_vol = "Expansion likely if put wall breaks with volume"
    else:
        signed, regime = 0, "between walls — dealer positioning likely dampening moves"
        expected_vol = "Compressed / range-bound behaviour expected between walls"

    direction = direction_from_score(signed) if signed else Direction.NEUTRAL
    result = AgentResult(
        name="Gamma Agent", score=to_public_score(signed) if signed else 20,
        direction=direction, confidence=0.5, weight=weight,
        reason=f"Gamma regime: {regime}.",
        evidence=evidence, timestamp=utcnow(),
    )
    metrics = {
        "call_wall": cw_strike, "put_wall": pw_strike, "gamma_flip": gamma_flip,
        "pinning_zone": pinning, "expected_volatility": expected_vol, "regime": regime,
        "net_gex": net_gex,
    }
    return result, metrics
