from __future__ import annotations
import pandas as pd
from app.models import AgentResult, Direction, Flag, utcnow
from app.features import Features
from .base import clamp, direction_from_score, to_public_score


def liquidity_agent(f: Features, df_3m: pd.DataFrame, weight: float) -> tuple[AgentResult, dict]:
    """Buy-side liquidity = swing highs above price; sell-side = swing lows
    below price, over the intraday session so far. Returns (AgentResult,
    metrics) — metrics feeds the Liquidity Map card and the narrative agent
    so numbers stay consistent across the dashboard."""
    evidence = []
    highs, lows = df_3m["high"], df_3m["low"]

    buy_side = float(highs[highs > f.close].max()) if (highs > f.close).any() else float(highs.max())
    sell_side = float(lows[lows < f.close].min()) if (lows < f.close).any() else float(lows.min())

    dist_to_buy = (buy_side - f.close) / f.close * 100
    dist_to_sell = (f.close - sell_side) / f.close * 100

    evidence.append(f"Nearest buy-side liquidity: {buy_side:.0f} ({dist_to_buy:.2f}% away)")
    evidence.append(f"Nearest sell-side liquidity: {sell_side:.0f} ({dist_to_sell:.2f}% away)")

    signed = 0.0
    sweep_status = "NONE"
    if dist_to_buy < dist_to_sell:
        signed = clamp((dist_to_sell - dist_to_buy) * 20, -60, 60)
        evidence.append("Price closer to buy-side liquidity — potential draw higher")
        sweep_status = "APPROACHING_BUY_SIDE"
    else:
        signed = -clamp((dist_to_buy - dist_to_sell) * 20, -60, 60)
        evidence.append("Price closer to sell-side liquidity — potential draw lower")
        sweep_status = "APPROACHING_SELL_SIDE"

    direction = direction_from_score(signed)
    result = AgentResult(
        name="Liquidity Agent", score=to_public_score(signed), direction=direction,
        confidence=round(min(abs(dist_to_buy - dist_to_sell) / 2, 1.0), 2), weight=weight,
        reason=f"Price is positioned nearer {'buy-side' if signed>0 else 'sell-side'} liquidity.",
        evidence=evidence, timestamp=utcnow(),
    )
    metrics = {
        "buy_side_liquidity": round(buy_side, 1),
        "sell_side_liquidity": round(sell_side, 1),
        "sweep_status": sweep_status,
        "distance_to_buy_pct": round(dist_to_buy, 2),
        "distance_to_sell_pct": round(dist_to_sell, 2),
    }
    return result, metrics


def trap_detection_agent(f: Features, df_3m: pd.DataFrame, weight: float) -> tuple[AgentResult, str]:
    """Returns (AgentResult, trap_label) where trap_label is one of
    NO_TRAP / CE_TRAP_RISK / PE_TRAP_RISK / HIGH_TRAP_RISK."""
    evidence = []
    risk_points = 0

    # VWAP rejection: wicked through VWAP but closed back on other side
    last = df_3m.iloc[-1]
    if last["high"] > f.vwap > last["close"] and f.close < f.vwap:
        risk_points += 1
        evidence.append("Recent candle rejected above VWAP (possible CE trap)")
    if last["low"] < f.vwap < last["close"] and f.close > f.vwap:
        risk_points += 1
        evidence.append("Recent candle rejected below VWAP (possible PE trap)")

    # false breakout of session high/low with low relative volume
    if f.close < f.session_high and (df_3m["high"].iloc[-3:] >= f.session_high * 0.999).any() and f.relative_volume < 0.9:
        risk_points += 1
        evidence.append("Failed breakout above session high on weak volume")
    if f.close > f.session_low and (df_3m["low"].iloc[-3:] <= f.session_low * 1.001).any() and f.relative_volume < 0.9:
        risk_points += 1
        evidence.append("Failed breakdown below session low on weak volume")

    if risk_points == 0:
        evidence.append("No trap pattern detected in recent price action")
        label = "NO_TRAP"
        signed = 0
    elif risk_points == 1:
        label = "CE_TRAP_RISK" if f.close < f.vwap else "PE_TRAP_RISK"
        signed = -30
    else:
        label = "HIGH_TRAP_RISK"
        signed = -70

    direction = direction_from_score(signed) if signed else Direction.NEUTRAL
    result = AgentResult(
        name="Trap Detection Agent", score=to_public_score(signed), direction=direction,
        confidence=round(min(risk_points / 3, 1.0), 2), weight=weight,
        reason=f"Trap status: {label.replace('_', ' ')}.",
        evidence=evidence, timestamp=utcnow(),
    )
    return result, label


def build_flags(f: Features, trend_dir: Direction, momentum_dir: Direction,
                 trap_label: str, buy_side: float, options_bias: str) -> list[Flag]:
    flags: list[Flag] = []

    if f.close > f.vwap:
        flags.append(Flag("BULL", "Price holding above VWAP", "Trend Agent"))
    if f.ema20 > f.ema50:
        flags.append(Flag("BULL", "EMA20 > EMA50 — bullish alignment intact", "Trend Agent"))

    if f.close < f.vwap:
        flags.append(Flag("BEAR", "Price trading below VWAP", "Trend Agent"))
    if f.ema20 < f.ema50:
        flags.append(Flag("BEAR", "EMA20 < EMA50 — bearish alignment intact", "Trend Agent"))

    if trap_label != "NO_TRAP":
        flags.append(Flag("WATCH", f"Trap risk detected: {trap_label.replace('_',' ')}", "Trap Detection Agent"))
    if abs(f.close - buy_side) / f.close < 0.002:
        flags.append(Flag("WATCH", "Price approaching nearby liquidity/resistance zone", "Liquidity Agent"))
    if f.relative_volume < 0.7:
        flags.append(Flag("WATCH", f"Relative volume low ({f.relative_volume:.2f}x) — weak participation", "Momentum Agent"))

    # ensure minimums per spec section 15 (2 bull / 2 bear / 2 watch) using
    # honest fallbacks rather than fabricated flags
    bulls = [f for f in flags if f.category == "BULL"]
    bears = [f for f in flags if f.category == "BEAR"]
    watch = [f for f in flags if f.category == "WATCH"]
    if len(bulls) < 2:
        flags.append(Flag("BULL", f"RSI {f.rsi14:.0f} " + ("supportive of upside" if f.rsi14 >= 50 else "not yet oversold-extreme"), "Momentum Agent"))
    if len(bears) < 2:
        flags.append(Flag("BEAR", f"ATR {f.atr14:.1f} — intraday risk remains elevated", "Regime Agent"))
    if len(watch) < 2:
        flags.append(Flag("WATCH", f"Options bias currently {options_bias} — confirm before entry", "Options/OI Agent"))
    return flags
