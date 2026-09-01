from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Any, Iterable

@dataclass(frozen=True)
class TradeObservation:
    pnl: float
    confidence: float
    regime: str = "UNKNOWN"
    strategy: str = "AI_COMPOSITE"
    agent_votes: dict[str, float] | None = None

def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0

def _max_drawdown(equity: list[float]) -> float:
    peak = equity[0] if equity else 0.0
    maximum = 0.0
    for value in equity:
        peak = max(peak, value)
        maximum = max(maximum, peak - value)
    return round(maximum, 4)

def performance_metrics(trades: Iterable[TradeObservation], initial_capital: float = 100000.0) -> dict[str, Any]:
    rows = list(trades)
    pnls = [float(x.pnl) for x in rows]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    equity = [float(initial_capital)]
    for pnl in pnls:
        equity.append(equity[-1] + pnl)
    expectancy = mean(pnls) if pnls else 0.0
    vol = pstdev(pnls) if len(pnls) > 1 else 0.0
    downside = pstdev([min(x, 0.0) for x in pnls]) if len(pnls) > 1 else 0.0
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    return {
        "trade_count": len(pnls), "wins": len(wins), "losses": len(losses),
        "win_rate": round(_safe_div(len(wins) * 100.0, len(pnls)), 2),
        "net_pnl": round(sum(pnls), 2), "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2), "profit_factor": round(_safe_div(gross_profit, gross_loss), 4),
        "expectancy": round(expectancy, 4), "average_win": round(mean(wins), 4) if wins else 0.0,
        "average_loss": round(mean(losses), 4) if losses else 0.0, "max_drawdown": _max_drawdown(equity),
        "sharpe_like": round(_safe_div(expectancy, vol) * sqrt(len(pnls)), 4) if pnls else 0.0,
        "sortino_like": round(_safe_div(expectancy, downside) * sqrt(len(pnls)), 4) if pnls else 0.0,
        "equity_curve": [round(x, 2) for x in equity],
    }

def confidence_calibration(trades: Iterable[TradeObservation], bucket_size: int = 10) -> dict[str, Any]:
    buckets: dict[int, list[TradeObservation]] = defaultdict(list)
    for item in trades:
        confidence = max(0.0, min(100.0, float(item.confidence)))
        buckets[min(90, int(confidence // bucket_size) * bucket_size)].append(item)
    output, weighted_error, total = [], 0.0, 0
    for bucket in sorted(buckets):
        items = buckets[bucket]
        actual = _safe_div(sum(1 for x in items if x.pnl > 0) * 100.0, len(items))
        predicted = mean(float(x.confidence) for x in items)
        error = abs(predicted - actual)
        weighted_error += error * len(items); total += len(items)
        output.append({"bucket": f"{bucket}-{bucket + bucket_size - 1}", "count": len(items),
                       "predicted_success_pct": round(predicted, 2), "actual_win_rate_pct": round(actual, 2),
                       "absolute_error": round(error, 2)})
    calibration_error = round(_safe_div(weighted_error, total), 2)
    return {"sample_count": total, "calibration_error": calibration_error, "buckets": output,
            "status": "CALIBRATED" if total >= 30 and calibration_error <= 10 else "LEARNING"}

def agent_performance(trades: Iterable[TradeObservation]) -> list[dict[str, Any]]:
    agg: dict[str, dict[str, float]] = defaultdict(lambda: {"weighted_pnl":0.0,"weight":0.0,"wins":0.0,"samples":0.0})
    for item in trades:
        for agent, vote in (item.agent_votes or {}).items():
            strength = min(1.0, max(0.0, abs(float(vote)) / 100.0))
            if not strength: continue
            row=agg[agent]; row["weighted_pnl"] += item.pnl*strength; row["weight"] += strength
            row["wins"] += (1.0 if item.pnl > 0 else 0.0)*strength; row["samples"] += 1
    out=[]
    for agent,row in agg.items():
        reliability=_safe_div(row["wins"]*100,row["weight"]); contribution=_safe_div(row["weighted_pnl"],row["weight"])
        out.append({"agent":agent,"samples":int(row["samples"]),"reliability_pct":round(reliability,2),
                    "average_weighted_pnl":round(contribution,2),
                    "status":"RELIABLE" if row["samples"]>=10 and reliability>=55 else "OBSERVE"})
    return sorted(out,key=lambda x:(x["reliability_pct"],x["average_weighted_pnl"]),reverse=True)

def grouped_performance(trades: Iterable[TradeObservation], field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[TradeObservation]] = defaultdict(list)
    for item in trades: grouped[getattr(item, field) or "UNKNOWN"].append(item)
    label = "regime" if field == "regime" else "strategy"
    rows=[]
    for name,items in grouped.items():
        metrics=performance_metrics(items)
        score=metrics["win_rate"]*0.4+min(metrics["profit_factor"],3)/3*35+max(-10,min(10,metrics["expectancy"]))/20*25
        rows.append({label:name,"score":round(max(0,min(100,score)),2),**metrics})
    return sorted(rows,key=lambda x:x["score"],reverse=True)

def walk_forward_splits(items: list[dict[str, Any]], train_size: int, test_size: int, step_size: int|None=None) -> list[dict[str, Any]]:
    if train_size<=0 or test_size<=0: raise ValueError("train_size and test_size must be positive")
    step=step_size or test_size
    if step<=0: raise ValueError("step_size must be positive")
    windows=[]; start=0; idx=1
    while start+train_size+test_size<=len(items):
        windows.append({"window":idx,"train_start":start,"train_end":start+train_size-1,
                        "test_start":start+train_size,"test_end":start+train_size+test_size-1,
                        "train":items[start:start+train_size],"test":items[start+train_size:start+train_size+test_size]})
        start+=step; idx+=1
    return windows
