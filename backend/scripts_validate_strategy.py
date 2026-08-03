"""CSV-driven conservative replay utility.
Usage: python scripts_validate_strategy.py candles.csv signals.csv
Candles: timestamp,open,high,low,close
Signals: signal_time,side,entry,stop_loss,target[,regime,grade]
"""
import json, sys
import pandas as pd
from app.strategy_validation import ReplayConfig, ReplaySignal, replay_signals, serialize_trades, summarize_trades

if len(sys.argv) != 3:
    raise SystemExit("Usage: python scripts_validate_strategy.py candles.csv signals.csv")
candles = pd.read_csv(sys.argv[1], parse_dates=["timestamp"]).set_index("timestamp")
raw = pd.read_csv(sys.argv[2])
signals = [ReplaySignal(
    signal_time=str(r.signal_time), side=str(r.side), entry=float(r.entry),
    stop_loss=float(r.stop_loss), target=float(r.target),
    regime=str(getattr(r, "regime", "UNKNOWN")), grade=str(getattr(r, "grade", "UNRATED")),
) for r in raw.itertuples(index=False)]
trades = replay_signals(candles, signals, ReplayConfig())
print(json.dumps({"summary": summarize_trades(trades), "trades": serialize_trades(trades)}, indent=2))
