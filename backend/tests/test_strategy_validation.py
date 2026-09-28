import pandas as pd
from app.strategy_validation import (
    ReplayConfig, ReplaySignal, certify_research_trials, deflated_sharpe_ratio,
    probabilistic_sharpe_ratio, purged_walk_forward_splits, replay_signals,
    summarize_trades, walk_forward_splits,
)


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


def test_purged_walk_forward_excludes_boundaries_and_prior_embargo():
    splits = purged_walk_forward_splits(24, 10, 4, 4, purge_size=2, embargo_size=2)
    assert splits[0]["train_indices"] == list(range(8))
    assert splits[0]["purged_indices"] == [8, 9]
    assert splits[0]["test_indices"] == [10, 11, 12, 13]
    assert splits[0]["embargoed_indices"] == [14, 15]
    assert set(splits[0]["embargoed_indices"]).isdisjoint(splits[1]["test_indices"])
    assert 14 not in splits[1]["train_indices"] and 15 not in splits[1]["train_indices"]


def test_probabilistic_and_deflated_sharpe_penalize_multiple_trials():
    selected = [0.01, 0.02, -0.005, 0.015, 0.01] * 8
    psr = probabilistic_sharpe_ratio(selected)
    dsr = deflated_sharpe_ratio(selected, [0.1, 0.2, 0.3, 0.4, 0.5])
    assert 0.5 < psr <= 1
    assert 0 <= dsr["deflated_sharpe_probability"] < psr
    assert dsr["trial_count"] == 5


def test_research_trial_certification_fails_closed_for_incomplete_history():
    report = certify_research_trials(
        [{"name": "a", "returns": [0.1, -0.1]}, {"name": "b", "returns": [0.2, -0.1]}],
        "a", min_observations=10,
    )
    assert report["status"] == "INSUFFICIENT_EVIDENCE"
    assert report["blockers"] == ["MINIMUM_OBSERVATIONS_NOT_MET"]


def test_research_trial_certification_can_approve_only_research_candidate():
    strong = [0.02, 0.015, 0.01, -0.002, 0.018] * 8
    weak = [0.001, -0.002, 0.0015, -0.001, 0.0005] * 8
    flat = [0.002, -0.002, 0.002, -0.002, 0.001] * 8
    report = certify_research_trials([
        {"name": "strong", "returns": strong},
        {"name": "weak", "returns": weak},
        {"name": "flat", "returns": flat},
    ], "strong", min_observations=30, min_probability=0.9)
    assert report["status"] == "CERTIFIED_RESEARCH_CANDIDATE"
    assert report["blockers"] == []
    assert report["trial_count"] == 3
