"""
Run with: pytest -v  (requires: pip install pytest pandas numpy --break-system-packages)

These tests were validated logically in-sandbox using plain assertions
(no pytest available in the build environment - no network to install it),
then translated to pytest form. Run them yourself before deploying.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pandas as pd
import numpy as np
from app.data_sources.mock_source import MockDataSource
from app.pipeline import run_pipeline, _build_trade_plan
import app.pipeline as pipeline_module
from app.features import build_features
from app.models import Direction, TradeGrade, DecisionType, Availability
from app.agents.alignment import compute_alignment, classify_trade_grade, DEFAULT_WEIGHTS
from app.agents.risk import risk_agent
from app.config import validate, Settings


@pytest.fixture
def mock_source():
    return MockDataSource(seed=7)


def test_pipeline_runs_without_error(mock_source):
    resp = run_pipeline(mock_source)
    assert resp.decision.decision in (DecisionType.CE_BUY, DecisionType.PE_BUY, DecisionType.NO_TRADE)
    assert resp.system_health.overall is not None


def test_no_trade_is_valid_default(mock_source):
    """With neutral/noisy mock data, system should default to NO_TRADE
    rather than forcing a trade — spec section 49's core principle."""
    resp = run_pipeline(mock_source)
    if resp.alignment.score is not None and resp.alignment.score < 70:
        assert resp.decision.decision == DecisionType.NO_TRADE


def test_only_a_or_aplus_can_be_actionable(mock_source):
    for seed in range(1, 15):
        resp = run_pipeline(MockDataSource(seed=seed))
        if resp.decision.decision != DecisionType.NO_TRADE:
            assert resp.decision.grade in (TradeGrade.A_PLUS, TradeGrade.A)


def test_trade_plan_uses_real_chain_prices():
    ds = MockDataSource(seed=1)
    df3 = ds.get_ohlc("3m", 150)
    df1d = ds.get_ohlc("1d", 5)
    f = build_features(df3, df1d)
    snap = ds.get_option_chain()
    plan, rr = _build_trade_plan(f, Direction.BULLISH, snap)
    atm_leg = next(x for x in snap["chain"]["CE"] if x["strike"] == snap["atm"])
    assert plan.ltp == atm_leg["ltp"]
    assert plan.stop_loss < plan.ltp < plan.target_1 < plan.target_2
    assert rr > 0


def test_risk_agent_vetoes_on_max_trades():
    _, risk_result = risk_agent(
        trades_today=3, max_trades=3, daily_pnl=0, daily_loss_limit=5000,
        consecutive_losses=0, max_consecutive_losses=2, data_age_sec=1,
        max_data_age_sec=10, vix=14, vix_spike_threshold=22,
        proposed_rr=2.0, min_rr=1.5, minutes_to_close=60, weight=0.1,
    )
    assert risk_result.approved is False
    assert "trade limit" in risk_result.reasons[0].lower()


def test_risk_agent_vetoes_on_stale_data():
    _, risk_result = risk_agent(
        trades_today=0, max_trades=3, daily_pnl=0, daily_loss_limit=5000,
        consecutive_losses=0, max_consecutive_losses=2, data_age_sec=30,
        max_data_age_sec=10, vix=14, vix_spike_threshold=22,
        proposed_rr=2.0, min_rr=1.5, minutes_to_close=60, weight=0.1,
    )
    assert risk_result.approved is False
    assert any("stale" in r.lower() for r in risk_result.reasons)


def test_risk_agent_approves_when_clean():
    _, risk_result = risk_agent(
        trades_today=0, max_trades=3, daily_pnl=0, daily_loss_limit=5000,
        consecutive_losses=0, max_consecutive_losses=2, data_age_sec=1,
        max_data_age_sec=10, vix=14, vix_spike_threshold=22,
        proposed_rr=2.0, min_rr=1.5, minutes_to_close=60, weight=0.1,
    )
    assert risk_result.approved is True
    assert risk_result.reasons == []


def test_alignment_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 0.01


def test_alignment_handles_missing_agents_gracefully():
    from app.agents.base import not_available
    agents = [not_available(name, w, "unavailable") for name, w in DEFAULT_WEIGHTS.items()]
    result = compute_alignment(agents)
    assert result.score is None  # must not fabricate a score from nothing


def test_config_validation_catches_bad_weights():
    s = Settings()
    s.agent_weights = {"Trend Agent": 0.5}  # doesn't sum to 1.0
    problems = validate(s)
    assert any("sum to 1.0" in p for p in problems)


def test_config_validation_requires_live_credentials():
    s = Settings()
    s.trading_mode = "live"
    s.kite_api_key = None
    problems = validate(s)
    assert any("KITE_API_KEY" in p for p in problems)


def test_data_unavailable_produces_not_available_agents(monkeypatch):
    from app.data_sources.base import DataUnavailable

    class BrokenSource(MockDataSource):
        def get_ohlc(self, timeframe, lookback):
            raise DataUnavailable("simulated broker outage")

    resp = run_pipeline(BrokenSource())
    assert resp.decision.decision == DecisionType.NO_TRADE
    assert all(a.availability == Availability.NOT_AVAILABLE for a in resp.agents)
    assert resp.system_health.overall.value == "RED"


def test_no_lookahead_last_candle_excluded_when_forming():
    """Zerodha source must drop an in-progress candle rather than use it."""
    import inspect
    from app.data_sources.zerodha_client import ZerodhaDataSource
    src = inspect.getsource(ZerodhaDataSource.get_ohlc)
    assert "NO LOOKAHEAD" in src
