from __future__ import annotations
from app.models import AgentResult, Direction, Availability, utcnow
from app.features import Features
from .base import clamp, direction_from_score, to_public_score


def trend_agent(f: Features, weight: float) -> AgentResult:
    signed = 0.0
    evidence = []

    if f.close > f.vwap:
        signed += 25
        evidence.append("Price holding above VWAP")
    else:
        signed -= 25
        evidence.append("Price trading below VWAP")

    if f.ema20 > f.ema50:
        signed += 25
        evidence.append("EMA20 > EMA50 (bullish alignment)")
    else:
        signed -= 25
        evidence.append("EMA20 < EMA50 (bearish alignment)")

    ema_gap_pct = (f.ema20 - f.ema50) / f.ema50 * 100
    signed += clamp(ema_gap_pct * 40, -25, 25)
    evidence.append(f"EMA20/EMA50 gap: {ema_gap_pct:+.2f}%")

    if f.close > f.day_open:
        signed += 15
        evidence.append("Trading above today's open")
    else:
        signed -= 15
        evidence.append("Trading below today's open")

    signed = clamp(signed, -100, 100)
    direction = direction_from_score(signed)
    return AgentResult(
        name="Trend Agent", score=to_public_score(signed), direction=direction,
        confidence=round(abs(signed) / 100, 2), weight=weight,
        reason=f"Price structure is {direction.value.lower()} relative to VWAP and EMA alignment.",
        evidence=evidence, timestamp=utcnow(),
    )


def momentum_agent(f: Features, weight: float) -> AgentResult:
    signed = 0.0
    evidence = []

    rsi_component = (f.rsi14 - 50) * 1.4
    signed += clamp(rsi_component, -40, 40)
    evidence.append(f"RSI(14): {f.rsi14:.1f}")

    macd_component = clamp(f.macd_hist * 30, -35, 35)
    signed += macd_component
    evidence.append(f"MACD histogram: {f.macd_hist:+.2f}")

    if f.rsi14 > 70:
        evidence.append("RSI overbought — momentum may be extended")
    elif f.rsi14 < 30:
        evidence.append("RSI oversold — momentum may be extended")

    if f.relative_volume > 1.3:
        boost = 25 if signed > 0 else -25
        signed += boost
        evidence.append(f"Relative volume {f.relative_volume:.2f}x confirms move")
    else:
        evidence.append(f"Relative volume {f.relative_volume:.2f}x — not yet confirming")

    signed = clamp(signed, -100, 100)
    direction = direction_from_score(signed)
    return AgentResult(
        name="Momentum Agent", score=to_public_score(signed), direction=direction,
        confidence=round(abs(signed) / 100, 2), weight=weight,
        reason=f"Momentum reads {direction.value.lower()} based on RSI/MACD with volume {'confirming' if f.relative_volume>1.3 else 'not yet confirming'}.",
        evidence=evidence, timestamp=utcnow(),
    )


def regime_agent(f: Features, weight: float) -> tuple[AgentResult, str]:
    """Classifies regime using ADX (trend strength) + ATR-relative volatility."""
    evidence = [f"ADX(14): {f.adx14:.1f}", f"ATR(14): {f.atr14:.2f}"]
    atr_pct = f.atr14 / f.close * 100
    evidence.append(f"ATR as % of price: {atr_pct:.2f}%")

    trending = f.adx14 > 25
    high_vol = atr_pct > 0.35

    signed = 0.0
    if trending:
        signed += 30 if f.close > f.vwap else -30
        evidence.append("ADX indicates a trending regime")
    else:
        evidence.append("ADX indicates range-bound conditions")

    if high_vol:
        evidence.append("Volatility elevated relative to recent range")

    signed = clamp(signed, -100, 100)
    if not trending and not high_vol:
        direction = Direction.NEUTRAL
        label = "RANGE"
    else:
        direction = direction_from_score(signed)
        if high_vol and trending:
            label = "STRONG_BULLISH" if signed > 0 else "STRONG_BEARISH"
        elif high_vol:
            label = "HIGH_VOLATILITY"
        else:
            label = "BULLISH" if signed > 0 else "BEARISH"

    result = AgentResult(
        name="Regime Agent", score=to_public_score(signed) if trending else 30,
        direction=direction, confidence=round(min(f.adx14 / 50, 1.0), 2), weight=weight,
        reason=f"Market regime classified as {label} (ADX {f.adx14:.0f}, ATR% {atr_pct:.2f}).",
        evidence=evidence, timestamp=utcnow(),
    )
    return result, label
