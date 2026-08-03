"""Conservative historical replay and walk-forward validation utilities.

This module never changes live strategy configuration and never places orders.
It is deliberately pessimistic where OHLC data cannot prove event ordering:
when stop and target are both touched in one candle, stop is assumed first.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Sequence
import math
import pandas as pd


@dataclass(frozen=True)
class ReplayConfig:
    initial_capital: float = 100000.0
    quantity: int = 1
    slippage_points: float = 0.0
    cost_rate: float = 0.0
    max_holding_bars: int = 75


@dataclass(frozen=True)
class ReplaySignal:
    signal_time: str
    side: str  # LONG or SHORT
    entry: float
    stop_loss: float
    target: float
    regime: str = "UNKNOWN"
    grade: str = "UNRATED"


@dataclass
class ReplayTrade:
    signal_time: str
    entry_time: str
    exit_time: str
    side: str
    regime: str
    grade: str
    entry_price: float
    exit_price: float
    quantity: int
    reason: str
    gross_pnl: float
    costs: float
    net_pnl: float
    bars_held: int


def _validate_candles(candles: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close"}
    missing = required.difference(candles.columns)
    if missing:
        raise ValueError(f"Missing candle columns: {sorted(missing)}")
    if candles.empty:
        raise ValueError("Candles cannot be empty")
    df = candles.copy().sort_index()
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError("Candle index must be unique and chronological")
    if df[list(required)].isnull().any().any():
        raise ValueError("Candles contain null OHLC values")
    invalid = (df["high"] < df[["open", "close", "low"]].max(axis=1)) | (
        df["low"] > df[["open", "close", "high"]].min(axis=1)
    )
    if invalid.any():
        raise ValueError("Invalid OHLC relationship detected")
    return df


def replay_signals(
    candles: pd.DataFrame,
    signals: Iterable[ReplaySignal],
    config: ReplayConfig | None = None,
) -> list[ReplayTrade]:
    """Replay signals without look-ahead bias.

    A signal produced at candle T can only enter at candle T+1 open. Entry is
    skipped if no later candle exists. Stops/targets are evaluated from the
    entry candle onward. Same-bar ambiguity is resolved against the strategy.
    """
    cfg = config or ReplayConfig()
    if cfg.quantity <= 0 or cfg.initial_capital <= 0 or cfg.max_holding_bars <= 0:
        raise ValueError("Replay configuration values must be positive")
    if cfg.slippage_points < 0 or cfg.cost_rate < 0:
        raise ValueError("Slippage and cost rate cannot be negative")

    df = _validate_candles(candles)
    index = pd.DatetimeIndex(pd.to_datetime(df.index))
    trades: list[ReplayTrade] = []

    for sig in signals:
        side = sig.side.upper()
        if side not in {"LONG", "SHORT"}:
            raise ValueError(f"Unsupported side: {sig.side}")
        ts = pd.Timestamp(sig.signal_time)
        pos = index.searchsorted(ts, side="right")  # strictly after signal
        if pos >= len(df):
            continue
        entry_bar = df.iloc[pos]
        raw_entry = float(entry_bar["open"])
        entry = raw_entry + cfg.slippage_points if side == "LONG" else raw_entry - cfg.slippage_points
        if side == "LONG" and not (sig.stop_loss < entry < sig.target):
            continue
        if side == "SHORT" and not (sig.target < entry < sig.stop_loss):
            continue

        exit_price = float(df.iloc[min(pos + cfg.max_holding_bars - 1, len(df) - 1)]["close"])
        exit_reason = "TIME_EXIT"
        exit_pos = min(pos + cfg.max_holding_bars - 1, len(df) - 1)

        for j in range(pos, min(pos + cfg.max_holding_bars, len(df))):
            bar = df.iloc[j]
            if side == "LONG":
                hit_stop = float(bar["low"]) <= sig.stop_loss
                hit_target = float(bar["high"]) >= sig.target
            else:
                hit_stop = float(bar["high"]) >= sig.stop_loss
                hit_target = float(bar["low"]) <= sig.target

            if hit_stop:  # pessimistic same-bar ordering
                exit_price = sig.stop_loss - cfg.slippage_points if side == "LONG" else sig.stop_loss + cfg.slippage_points
                exit_reason = "STOP_LOSS"
                exit_pos = j
                break
            if hit_target:
                exit_price = sig.target - cfg.slippage_points if side == "LONG" else sig.target + cfg.slippage_points
                exit_reason = "TARGET"
                exit_pos = j
                break

        direction = 1 if side == "LONG" else -1
        gross = (exit_price - entry) * direction * cfg.quantity
        turnover = (abs(entry) + abs(exit_price)) * cfg.quantity
        costs = turnover * cfg.cost_rate
        net = gross - costs
        trades.append(ReplayTrade(
            signal_time=str(ts), entry_time=str(index[pos]), exit_time=str(index[exit_pos]),
            side=side, regime=sig.regime, grade=sig.grade,
            entry_price=round(entry, 4), exit_price=round(exit_price, 4), quantity=cfg.quantity,
            reason=exit_reason, gross_pnl=round(gross, 2), costs=round(costs, 2),
            net_pnl=round(net, 2), bars_held=exit_pos - pos + 1,
        ))
    return trades


def summarize_trades(trades: Sequence[ReplayTrade], initial_capital: float = 100000.0) -> dict:
    if initial_capital <= 0:
        raise ValueError("Initial capital must be positive")
    if not trades:
        return {"total": 0, "note": "No replayable trades."}
    pnls = [t.net_pnl for t in trades]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    equity = initial_capital
    peak = equity
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    by_regime: dict[str, dict] = {}
    for trade in trades:
        bucket = by_regime.setdefault(trade.regime, {"trades": 0, "net_pnl": 0.0, "wins": 0})
        bucket["trades"] += 1
        bucket["net_pnl"] += trade.net_pnl
        bucket["wins"] += int(trade.net_pnl > 0)
    for bucket in by_regime.values():
        bucket["net_pnl"] = round(bucket["net_pnl"], 2)
        bucket["win_rate"] = round(bucket["wins"] / bucket["trades"] * 100, 2)
    avg = sum(pnls) / len(pnls)
    variance = sum((x - avg) ** 2 for x in pnls) / len(pnls)
    return {
        "total": len(trades), "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 2),
        "net_pnl": round(sum(pnls), 2), "ending_capital": round(equity, 2),
        "expectancy": round(avg, 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd / peak * 100, 2) if peak else None,
        "pnl_stddev": round(math.sqrt(variance), 2), "by_regime": by_regime,
        "note": "Descriptive validation only; no automatic strategy promotion.",
    }


def walk_forward_splits(length: int, train_size: int, test_size: int, step_size: int | None = None) -> list[dict]:
    """Return expanding chronological train/test indices with no overlap leakage."""
    if min(length, train_size, test_size) <= 0:
        raise ValueError("length, train_size and test_size must be positive")
    step = step_size or test_size
    if step <= 0:
        raise ValueError("step_size must be positive")
    splits = []
    train_end = train_size
    while train_end + test_size <= length:
        splits.append({
            "train_start": 0, "train_end": train_end,
            "test_start": train_end, "test_end": train_end + test_size,
        })
        train_end += step
    return splits


def serialize_trades(trades: Sequence[ReplayTrade]) -> list[dict]:
    return [asdict(t) for t in trades]
