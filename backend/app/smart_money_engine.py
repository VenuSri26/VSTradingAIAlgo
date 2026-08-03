from __future__ import annotations
from typing import Any


def analyse_market_structure(candles: list[dict[str, Any]]) -> dict[str, Any]:
    clean = [c for c in candles if all(k in c for k in ("open", "high", "low", "close"))]
    if len(clean) < 5:
        return {
            "structure_bias": "NEUTRAL", "structure_score": 50.0,
            "bos": None, "choch": None, "liquidity_sweeps": [],
            "fair_value_gaps": [], "order_blocks": [],
            "premium_discount": "UNKNOWN", "confidence": 20.0,
            "warnings": ["At least five candles are required"],
        }

    recent = clean[-20:]
    highs = [float(c["high"]) for c in recent]
    lows = [float(c["low"]) for c in recent]
    closes = [float(c["close"]) for c in recent]
    last = recent[-1]
    prior = recent[:-1]
    prior_high = max(float(c["high"]) for c in prior[-8:])
    prior_low = min(float(c["low"]) for c in prior[-8:])

    bos = "BULLISH" if float(last["close"]) > prior_high else "BEARISH" if float(last["close"]) < prior_low else None
    earlier_bias = "BULLISH" if closes[-4] > closes[-5] else "BEARISH"
    current_bias = "BULLISH" if closes[-1] > closes[-2] else "BEARISH"
    choch = current_bias if current_bias != earlier_bias and bos == current_bias else None

    sweeps: list[dict[str, Any]] = []
    if float(last["high"]) > prior_high and float(last["close"]) < prior_high:
        sweeps.append({"side": "BUY_SIDE", "level": prior_high})
    if float(last["low"]) < prior_low and float(last["close"]) > prior_low:
        sweeps.append({"side": "SELL_SIDE", "level": prior_low})

    fvgs: list[dict[str, Any]] = []
    for i in range(2, len(recent)):
        a, c = recent[i - 2], recent[i]
        if float(c["low"]) > float(a["high"]):
            fvgs.append({"type": "BULLISH", "low": float(a["high"]), "high": float(c["low"])})
        elif float(c["high"]) < float(a["low"]):
            fvgs.append({"type": "BEARISH", "low": float(c["high"]), "high": float(a["low"])})
    fvgs = fvgs[-5:]

    order_blocks: list[dict[str, Any]] = []
    if bos:
        for candle in reversed(prior[-6:]):
            bearish = float(candle["close"]) < float(candle["open"])
            bullish = float(candle["close"]) > float(candle["open"])
            if bos == "BULLISH" and bearish:
                order_blocks.append({"type": "BULLISH", "low": float(candle["low"]), "high": float(candle["high"])})
                break
            if bos == "BEARISH" and bullish:
                order_blocks.append({"type": "BEARISH", "low": float(candle["low"]), "high": float(candle["high"])})
                break

    range_high, range_low = max(highs), min(lows)
    midpoint = (range_high + range_low) / 2
    premium_discount = "PREMIUM" if closes[-1] > midpoint else "DISCOUNT"

    score = 50.0
    if bos == "BULLISH": score += 22
    if bos == "BEARISH": score -= 22
    if choch == "BULLISH": score += 10
    if choch == "BEARISH": score -= 10
    if any(s["side"] == "SELL_SIDE" for s in sweeps): score += 8
    if any(s["side"] == "BUY_SIDE" for s in sweeps): score -= 8
    structure_bias = "BULLISH" if score >= 58 else "BEARISH" if score <= 42 else "NEUTRAL"
    confidence = min(100.0, 35.0 + (20 if bos else 0) + (15 if choch else 0) + len(sweeps) * 10 + min(len(fvgs), 2) * 5)

    return {
        "structure_bias": structure_bias,
        "structure_score": round(max(0.0, min(100.0, score)), 2),
        "bos": bos, "choch": choch,
        "liquidity_sweeps": sweeps,
        "fair_value_gaps": fvgs,
        "order_blocks": order_blocks,
        "premium_discount": premium_discount,
        "range": {"high": range_high, "low": range_low, "midpoint": midpoint},
        "confidence": round(confidence, 2), "warnings": [],
    }
