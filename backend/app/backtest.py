"""
Backtesting / self-learning evaluation scaffold (spec sections 40-41).

Explicitly NOT an auto-optimizer — per spec section 41, "no strategy should
automatically go live merely because its backtest looks profitable." This
module only measures what already happened against what the audit log
recorded was planned; a human reviews the results.

Works against ANY price series (mock-generated OHLC today, real Zerodha
historical candles once you're live) — decoupled from the data source on
purpose so the same evaluation code is valid in both modes.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Iterable, Optional
import pandas as pd


@dataclass
class TradeEvaluation:
    timestamp: str
    decision: str          # CE_BUY | PE_BUY
    grade: str
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    outcome: str            # HIT_T1 | HIT_T2 | HIT_SL | NO_TOUCH | INVALID
    mfe: float               # max favourable excursion, in premium points
    mae: float               # max adverse excursion, in premium points
    realized_rr: Optional[float]


def load_audit_log(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def evaluate_trade(plan: dict, forward_prices: pd.Series) -> TradeEvaluation:
    """forward_prices: the option's LTP series AFTER entry, oldest-first, in
    the order candles actually occurred (no lookahead — only pass prices
    that occurred after the logged decision timestamp)."""
    entry = plan["ltp"]
    sl = plan["stop_loss"]
    t1 = plan["target_1"]
    t2 = plan["target_2"]

    if entry is None or sl is None or t1 is None:
        return TradeEvaluation("", "", "", entry or 0, sl or 0, t1 or 0, t2 or 0, "INVALID", 0, 0, None)

    mfe, mae = 0.0, 0.0
    outcome = "NO_TOUCH"
    for price in forward_prices:
        mfe = max(mfe, price - entry)
        mae = max(mae, entry - price)
        if price <= sl:
            outcome = "HIT_SL"
            break
        if t2 is not None and price >= t2:
            outcome = "HIT_T2"
            break
        if price >= t1:
            outcome = "HIT_T1"
            break

    realized_rr = None
    risk = entry - sl
    if risk > 0:
        if outcome == "HIT_T1":
            realized_rr = round((t1 - entry) / risk, 2)
        elif outcome == "HIT_T2":
            realized_rr = round((t2 - entry) / risk, 2)
        elif outcome == "HIT_SL":
            realized_rr = -1.0

    return TradeEvaluation(
        timestamp="", decision="", grade="", entry=entry, stop_loss=sl,
        target_1=t1, target_2=t2 or 0, outcome=outcome,
        mfe=round(mfe, 2), mae=round(mae, 2), realized_rr=realized_rr,
    )


def evaluate_audit_log(records: Iterable[dict], price_lookup) -> list[TradeEvaluation]:
    """price_lookup: callable(timestamp: str, plan: dict) -> pd.Series of
    forward prices for that trade, or None if unavailable. Kept as an
    injected function so this module never fetches data itself — caller
    decides whether that's mock or real Zerodha historical data."""
    results = []
    for rec in records:
        if rec.get("outcome_status") != "GENERATED" or not rec.get("plan"):
            continue
        forward_prices = price_lookup(rec["timestamp"], rec["plan"])
        if forward_prices is None or len(forward_prices) == 0:
            continue
        ev = evaluate_trade(rec["plan"], forward_prices)
        ev.timestamp = rec["timestamp"]
        ev.decision = rec["decision"]
        ev.grade = rec["grade"]
        results.append(ev)
    return results


def summarize(evaluations: list[TradeEvaluation]) -> dict:
    if not evaluations:
        return {"total": 0, "note": "No evaluable trades yet — need GENERATED decisions plus forward price data."}
    wins = [e for e in evaluations if e.outcome in ("HIT_T1", "HIT_T2")]
    losses = [e for e in evaluations if e.outcome == "HIT_SL"]
    rr_values = [e.realized_rr for e in evaluations if e.realized_rr is not None]
    by_grade: dict[str, dict] = {}
    for e in evaluations:
        g = by_grade.setdefault(e.grade, {"total": 0, "wins": 0})
        g["total"] += 1
        if e.outcome in ("HIT_T1", "HIT_T2"):
            g["wins"] += 1
    for g in by_grade.values():
        g["win_rate"] = round(g["wins"] / g["total"] * 100, 1) if g["total"] else None

    return {
        "total": len(evaluations),
        "wins": len(wins),
        "losses": len(losses),
        "no_touch": len(evaluations) - len(wins) - len(losses),
        "win_rate": round(len(wins) / len(evaluations) * 100, 1) if evaluations else None,
        "avg_realized_rr": round(sum(rr_values) / len(rr_values), 2) if rr_values else None,
        "avg_mfe": round(sum(e.mfe for e in evaluations) / len(evaluations), 2),
        "avg_mae": round(sum(e.mae for e in evaluations) / len(evaluations), 2),
        "by_grade": by_grade,
        "note": "Descriptive only — per spec section 41, no strategy change should be automated from this output.",
    }
