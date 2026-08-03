from __future__ import annotations
from typing import Any


def classify_market_regime(market: dict[str, Any], indicators: dict[str, Any], levels: dict[str, Any] | None = None) -> dict[str, Any]:
    levels = levels or {}
    spot = float(market.get("nifty_spot") or market.get("spot") or 0.0)
    vwap = float(indicators.get("vwap") or 0.0)
    ema20 = float(indicators.get("ema20") or 0.0)
    ema50 = float(indicators.get("ema50") or 0.0)
    atr = float(indicators.get("atr") or 0.0)
    adx = float(indicators.get("adx") or 0.0)
    rsi = float(indicators.get("rsi") or 50.0)

    trend_score = 50.0
    reasons: list[str] = []
    if spot and vwap:
        if spot > vwap:
            trend_score += 10
            reasons.append("Spot is above VWAP")
        elif spot < vwap:
            trend_score -= 10
            reasons.append("Spot is below VWAP")
    if ema20 and ema50:
        if ema20 > ema50:
            trend_score += 15
            reasons.append("EMA20 is above EMA50")
        elif ema20 < ema50:
            trend_score -= 15
            reasons.append("EMA20 is below EMA50")
    if rsi >= 60:
        trend_score += 8
    elif rsi <= 40:
        trend_score -= 8

    atr_pct = round((atr / spot * 100), 3) if spot and atr else 0.0
    volatility = "HIGH" if atr_pct >= 0.45 else "LOW" if atr_pct <= 0.18 else "NORMAL"

    if adx >= 25:
        regime = "TRENDING_BULLISH" if trend_score >= 55 else "TRENDING_BEARISH"
    elif adx <= 18:
        regime = "RANGE_BOUND"
    else:
        orh = float(levels.get("orh") or 0.0)
        orl = float(levels.get("orl") or 0.0)
        if spot and orh and spot > orh:
            regime = "BREAKOUT_BULLISH"
        elif spot and orl and spot < orl:
            regime = "BREAKOUT_BEARISH"
        else:
            regime = "TRANSITION"

    if volatility == "HIGH":
        reasons.append("ATR indicates high volatility")
    elif volatility == "LOW":
        reasons.append("ATR indicates compressed volatility")

    confidence = min(100.0, 45.0 + abs(trend_score - 50.0) + min(adx, 35.0))
    return {
        "regime": regime,
        "volatility": volatility,
        "trend_score": round(max(0.0, min(100.0, trend_score)), 2),
        "adx": round(adx, 2),
        "atr_pct": atr_pct,
        "confidence": round(confidence, 2),
        "reasons": reasons or ["Insufficient directional evidence"],
    }
