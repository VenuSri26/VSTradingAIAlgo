from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class OptionChainSummary:
    spot: float
    atm_strike: int
    expiry: str | None
    total_ce_oi: int
    total_pe_oi: int
    total_ce_oi_change: int
    total_pe_oi_change: int
    pcr_oi: float | None
    pcr_change: float | None
    call_wall: int | None
    put_wall: int | None
    max_pain: int | None
    strongest_resistance: int | None
    strongest_support: int | None
    institutional_bias: str
    bias_score: int
    confidence: int
    reasons: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_legs(snapshot: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chain = snapshot.get("chain") or {}
    ce = list(chain.get("CE") or [])
    pe = list(chain.get("PE") or [])
    return ce, pe


def calculate_max_pain(ce: list[dict[str, Any]], pe: list[dict[str, Any]]) -> int | None:
    strikes = sorted({*_safe_strikes(ce), *_safe_strikes(pe)})
    if not strikes:
        return None
    ce_by_strike = {_safe_int(row.get("strike")): max(0, _safe_int(row.get("oi"))) for row in ce}
    pe_by_strike = {_safe_int(row.get("strike")): max(0, _safe_int(row.get("oi"))) for row in pe}
    pains: dict[int, float] = {}
    for settle in strikes:
        call_pain = sum(max(0, settle - strike) * oi for strike, oi in ce_by_strike.items())
        put_pain = sum(max(0, strike - settle) * oi for strike, oi in pe_by_strike.items())
        pains[settle] = call_pain + put_pain
    return min(pains, key=pains.get)


def _safe_strikes(rows: list[dict[str, Any]]) -> set[int]:
    return {_safe_int(row.get("strike")) for row in rows if _safe_int(row.get("strike")) > 0}


def analyse_option_chain(snapshot: dict[str, Any]) -> dict[str, Any]:
    ce, pe = _normalise_legs(snapshot)
    spot = _safe_float(snapshot.get("spot"))
    atm = _safe_int(snapshot.get("atm")) or (round(spot / 50) * 50 if spot else 0)
    expiry = snapshot.get("expiry")
    warnings: list[str] = []

    if not ce or not pe:
        warnings.append("Option-chain legs are incomplete")
    if not spot:
        warnings.append("Spot price is unavailable")

    total_ce_oi = sum(max(0, _safe_int(row.get("oi"))) for row in ce)
    total_pe_oi = sum(max(0, _safe_int(row.get("oi"))) for row in pe)
    total_ce_change = sum(_safe_int(row.get("oi_change")) for row in ce)
    total_pe_change = sum(_safe_int(row.get("oi_change")) for row in pe)

    pcr_oi = round(total_pe_oi / total_ce_oi, 3) if total_ce_oi else None
    pcr_change = round(total_pe_change / abs(total_ce_change), 3) if total_ce_change else None

    call_wall_row = max(ce, key=lambda row: _safe_int(row.get("oi")), default=None)
    put_wall_row = max(pe, key=lambda row: _safe_int(row.get("oi")), default=None)
    call_wall = _safe_int(call_wall_row.get("strike")) if call_wall_row else None
    put_wall = _safe_int(put_wall_row.get("strike")) if put_wall_row else None
    max_pain = calculate_max_pain(ce, pe)

    score = 50
    reasons: list[str] = []
    available_signals = 0

    if pcr_oi is not None:
        available_signals += 1
        if pcr_oi >= 1.15:
            score += 18
            reasons.append(f"Put OI dominates with PCR {pcr_oi:.2f}")
        elif pcr_oi <= 0.80:
            score -= 18
            reasons.append(f"Call OI dominates with PCR {pcr_oi:.2f}")
        else:
            reasons.append(f"PCR {pcr_oi:.2f} is balanced")

    if total_pe_change or total_ce_change:
        available_signals += 1
        delta = total_pe_change - total_ce_change
        scale = max(abs(total_pe_change) + abs(total_ce_change), 1)
        contribution = max(-15, min(15, round(delta / scale * 15)))
        score += contribution
        if contribution > 3:
            reasons.append("Put-side OI change is stronger than call-side change")
        elif contribution < -3:
            reasons.append("Call-side OI change is stronger than put-side change")
        else:
            reasons.append("OI change is broadly balanced")

    if spot and put_wall:
        available_signals += 1
        if put_wall <= spot and spot - put_wall <= 200:
            score += 8
            reasons.append(f"Put wall {put_wall} provides nearby support")
        elif put_wall > spot:
            score -= 4
            reasons.append(f"Put wall {put_wall} is above spot and offers weak support")

    if spot and call_wall:
        available_signals += 1
        if call_wall >= spot and call_wall - spot <= 200:
            score -= 8
            reasons.append(f"Call wall {call_wall} creates nearby resistance")
        elif call_wall < spot:
            score += 4
            reasons.append(f"Spot is above call wall {call_wall}")

    if spot and max_pain:
        available_signals += 1
        distance = spot - max_pain
        if distance >= 100:
            score -= 5
            reasons.append(f"Spot is {distance:.0f} points above max pain")
        elif distance <= -100:
            score += 5
            reasons.append(f"Spot is {abs(distance):.0f} points below max pain")
        else:
            reasons.append("Spot is close to max pain")

    score = max(0, min(100, int(round(score))))
    if score >= 62:
        bias = "BULLISH"
    elif score <= 38:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"
    confidence = max(10, min(100, round((available_signals / 5) * 100)))
    if warnings:
        confidence = min(confidence, 40)

    summary = OptionChainSummary(
        spot=round(spot, 2),
        atm_strike=atm,
        expiry=expiry,
        total_ce_oi=total_ce_oi,
        total_pe_oi=total_pe_oi,
        total_ce_oi_change=total_ce_change,
        total_pe_oi_change=total_pe_change,
        pcr_oi=pcr_oi,
        pcr_change=pcr_change,
        call_wall=call_wall,
        put_wall=put_wall,
        max_pain=max_pain,
        strongest_resistance=call_wall,
        strongest_support=put_wall,
        institutional_bias=bias,
        bias_score=score,
        confidence=confidence,
        reasons=reasons[:8],
        warnings=warnings,
    )
    return summary.to_dict()
