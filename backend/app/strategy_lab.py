from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import numpy as np

from app.strategy_validation import ReplayConfig, ReplaySignal, replay_signals, summarize_trades, walk_forward_splits


def _json_safe(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def validate_strategy(payload: dict[str, Any]) -> dict:
    candles = payload.get("candles") or []
    signals = payload.get("signals") or []
    if len(candles) < 2:
        raise ValueError("At least two candles are required")
    required = {"timestamp", "open", "high", "low", "close"}
    if any(not required.issubset(c) for c in candles):
        raise ValueError("Every candle requires timestamp, open, high, low and close")
    frame = pd.DataFrame(candles)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.set_index("timestamp").sort_index()
    replay_signals_input = [
        ReplaySignal(
            signal_time=str(s["signal_time"]), side=str(s["side"]),
            entry=float(s.get("entry", 0)), stop_loss=float(s["stop_loss"]), target=float(s["target"]),
            regime=str(s.get("regime", "UNKNOWN")), grade=str(s.get("grade", "UNRATED")),
        ) for s in signals
    ]
    config_data = payload.get("config") or {}
    config = ReplayConfig(
        quantity=int(config_data.get("quantity", 1)),
        slippage_points=float(config_data.get("slippage_points", 0)),
        cost_rate=float(config_data.get("cost_rate", 0)),
        initial_capital=float(config_data.get("initial_capital", 100000)),
        max_holding_bars=int(config_data.get("max_holding_bars", 30)),
    )
    trades = replay_signals(frame, replay_signals_input, config)
    summary = summarize_trades(trades, initial_capital=config.initial_capital)
    wf = payload.get("walk_forward") or {}
    splits = walk_forward_splits(
        len(frame), int(wf.get("train_size", max(1, len(frame) // 2))),
        int(wf.get("test_size", max(1, len(frame) // 4))),
        int(wf.get("step_size", max(1, len(frame) // 4))),
    ) if wf.get("enabled") and len(frame) >= 4 else []
    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "name": str(payload.get("name") or "Unnamed Strategy"),
        "summary": summary,
        "trades": _json_safe([asdict(t) for t in trades]),
        "walk_forward_splits": _json_safe(splits),
        "config": asdict(config),
        "promotion_status": "RESEARCH_ONLY",
        "note": "Results are descriptive. Production weights and execution are never changed automatically.",
    }


def sample_payload() -> dict:
    times = pd.date_range("2026-01-05 09:15", periods=12, freq="3min", tz="Asia/Kolkata")
    prices = [100, 101, 103, 102, 104, 106, 108, 107, 109, 111, 110, 112]
    candles = []
    for ts, close in zip(times, prices):
        candles.append({"timestamp": ts.isoformat(), "open": close - 0.5, "high": close + 1.5, "low": close - 1.5, "close": close})
    return {
        "name": "Sample Momentum Validation",
        "candles": candles,
        "signals": [{"signal_time": times[1].isoformat(), "side": "LONG", "entry": 101, "stop_loss": 99, "target": 107, "regime": "TREND", "grade": "A"}],
        "config": {"quantity": 75, "slippage_points": 0.25, "cost_rate": 0.0015, "initial_capital": 100000, "max_holding_bars": 8},
        "walk_forward": {"enabled": True, "train_size": 6, "test_size": 3, "step_size": 3},
    }
