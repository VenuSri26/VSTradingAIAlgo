"""
Institutional Narrative Agent (spec section 23).

Deliberately template-based rather than an LLM call: every clause is sourced
directly from a real computed value (regime, levels, options metrics,
liquidity), so the narrative can never say something the data doesn't
support. Kept to ~3-4 sentences per spec.
"""
from __future__ import annotations
from app.features import Features


def build_narrative(f: Features, regime_label: str, trend_direction: str,
                     oi_metrics: dict, buy_side_liq: float, sell_side_liq: float,
                     trap_label: str) -> str:
    parts = []

    vwap_rel = "above" if f.close > f.vwap else "below"
    regime_readable = regime_label.replace("_", " ").lower()
    parts.append(
        f"Nifty is trading {vwap_rel} VWAP in a {regime_readable} regime, "
        f"with price action reading {trend_direction.lower()}."
    )

    call_wall = oi_metrics.get("call_wall")
    put_wall = oi_metrics.get("put_wall")
    if call_wall and put_wall:
        parts.append(
            f"Options positioning shows the call wall at {call_wall['strike']} and put wall at "
            f"{put_wall['strike']}, with PCR at {oi_metrics.get('pcr', 'N/A')}."
        )

    dist_buy = abs(buy_side_liq - f.close) / f.close * 100
    dist_sell = abs(f.close - sell_side_liq) / f.close * 100
    nearer = "buy-side" if dist_buy < dist_sell else "sell-side"
    parts.append(f"The index is closer to {nearer} liquidity, which may act as a magnet for the next move.")

    if trap_label != "NO_TRAP":
        parts.append(f"Note: current price action carries {trap_label.replace('_', ' ').lower()} conditions — confirmation is advised before acting.")

    return " ".join(parts)
