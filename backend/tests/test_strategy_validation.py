import pandas as pd
from app.strategy_validation import ReplayConfig, ReplaySignal, replay_signals, summarize_trades, walk_forward_splits


def candles(rows):
    idx = pd.date_range("2026-01-01 09:15", periods=len(rows), freq="3min", tz="Asia/Kolkata")
    return pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close"])


def test_next_bar_entry_prevents_lookahead():
    df = candles([(100,101,99,100), (110,116,109,115), (115,121,114,120)])
    sig = ReplaySignal(str(df.index[0]), "LONG", 100, 105, 120)
    trades = replay_signals(df, [sig])
    assert trades[0].entry_price == 110
    assert trades[0].reason == "TARGET"


def test_same_bar_stop_target_conflict_is_stop():
    df = candles([(100,101,99,100), (100,111,94,105)])
    sig = ReplaySignal(str(df.index[0]), "LONG", 100, 95, 110)
    trade = replay_signals(df, [sig])[0]
    assert trade.reason == "STOP_LOSS"
    assert trade.net_pnl < 0


def test_costs_and_slippage_reduce_pnl():
    df = candles([(100,101,99,100), (100,111,99,110)])
    sig = ReplaySignal(str(df.index[0]), "LONG", 100, 95, 110)
    trade = replay_signals(df, [sig], ReplayConfig(quantity=10, slippage_points=1, cost_rate=.001))[0]
    assert trade.entry_price == 101
    assert trade.exit_price == 109
    assert trade.costs > 0
    assert trade.net_pnl < trade.gross_pnl


def test_summary_has_drawdown_and_regime_metrics():
    df = candles([(100,101,99,100),(100,111,99,110),(110,111,109,110),(110,111,99,100)])
    signals = [
        ReplaySignal(str(df.index[0]), "LONG",100,95,110,"TREND"),
        ReplaySignal(str(df.index[2]), "LONG",110,105,120,"RANGE"),
    ]
    result = summarize_trades(replay_signals(df, signals))
    assert result["total"] == 2
    assert "TREND" in result["by_regime"]
    assert result["max_drawdown"] >= 0


def test_walk_forward_splits_are_chronological():
    splits = walk_forward_splits(100, 40, 20, 20)
    assert splits == [
        {"train_start":0,"train_end":40,"test_start":40,"test_end":60},
        {"train_start":0,"train_end":60,"test_start":60,"test_end":80},
        {"train_start":0,"train_end":80,"test_start":80,"test_end":100},
    ]
