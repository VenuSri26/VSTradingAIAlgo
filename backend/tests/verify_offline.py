"""
Offline, dependency-light verification of the core pipeline logic — the
same assertions as test_pipeline.py, written in plain Python instead of
pytest, so they can be run with zero extra installs:

    python3 tests/verify_offline.py

Use `pytest -v` for the full formal test report once pytest is installed
(it's in requirements.txt); use this script for a quick sanity check.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.data_sources.mock_source import MockDataSource
from app.pipeline import run_pipeline, _build_trade_plan
from app.features import build_features
from app.models import Direction, TradeGrade, DecisionType, Availability
from app.agents.alignment import compute_alignment, DEFAULT_WEIGHTS
from app.agents.risk import risk_agent
from app.config import validate, Settings
from app.data_sources.base import DataUnavailable

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}")

resp = run_pipeline(MockDataSource(seed=7))
check("pipeline_runs", resp.decision.decision in (DecisionType.CE_BUY, DecisionType.PE_BUY, DecisionType.NO_TRADE))

only_a_ok = True
for seed in range(1, 15):
    r = run_pipeline(MockDataSource(seed=seed))
    if r.decision.decision != DecisionType.NO_TRADE and r.decision.grade not in (TradeGrade.A_PLUS, TradeGrade.A):
        only_a_ok = False
check("only_A_or_Aplus_actionable", only_a_ok)

ds = MockDataSource(seed=1)
df3 = ds.get_ohlc("3m", 150); df1d = ds.get_ohlc("1d", 5)
f = build_features(df3, df1d)
snap = ds.get_option_chain()
plan, rr = _build_trade_plan(f, Direction.BULLISH, snap)
atm_leg = next(x for x in snap["chain"]["CE"] if x["strike"] == snap["atm"])
check("plan_uses_real_chain_price", plan.ltp == atm_leg["ltp"])
check("plan_sl_lt_ltp_lt_targets", plan.stop_loss < plan.ltp < plan.target_1 < plan.target_2)
check("plan_positive_rr", rr > 0)

_, risk_result = risk_agent(trades_today=3, max_trades=3, daily_pnl=0, daily_loss_limit=5000,
    consecutive_losses=0, max_consecutive_losses=2, data_age_sec=1, max_data_age_sec=10,
    vix=14, vix_spike_threshold=22, proposed_rr=2.0, min_rr=1.5, minutes_to_close=60, weight=0.1)
check("risk_vetoes_max_trades", risk_result.approved is False)

_, risk_result2 = risk_agent(trades_today=0, max_trades=3, daily_pnl=0, daily_loss_limit=5000,
    consecutive_losses=0, max_consecutive_losses=2, data_age_sec=30, max_data_age_sec=10,
    vix=14, vix_spike_threshold=22, proposed_rr=2.0, min_rr=1.5, minutes_to_close=60, weight=0.1)
check("risk_vetoes_stale_data", risk_result2.approved is False)

_, risk_result3 = risk_agent(trades_today=0, max_trades=3, daily_pnl=0, daily_loss_limit=5000,
    consecutive_losses=0, max_consecutive_losses=2, data_age_sec=1, max_data_age_sec=10,
    vix=14, vix_spike_threshold=22, proposed_rr=2.0, min_rr=1.5, minutes_to_close=60, weight=0.1)
check("risk_approves_when_clean", risk_result3.approved is True and risk_result3.reasons == [])

check("weights_sum_to_one", abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 0.01)

from app.agents.base import not_available
agents = [not_available(name, w, "unavailable") for name, w in DEFAULT_WEIGHTS.items()]
result = compute_alignment(agents)
check("alignment_none_when_all_unavailable", result.score is None)

s = Settings(); s.agent_weights = {"Trend Agent": 0.5}
problems = validate(s)
check("config_catches_bad_weights", any("sum to 1.0" in p for p in problems))

s2 = Settings(); s2.trading_mode = "live"; s2.kite_api_key = None
problems2 = validate(s2)
check("config_requires_live_creds", any("KITE_API_KEY" in p for p in problems2))

class BrokenSource(MockDataSource):
    def get_ohlc(self, timeframe, lookback):
        raise DataUnavailable("simulated broker outage")

resp2 = run_pipeline(BrokenSource())
check("data_unavailable_no_trade", resp2.decision.decision == DecisionType.NO_TRADE)
check("data_unavailable_agents_flagged", all(a.availability == Availability.NOT_AVAILABLE for a in resp2.agents))
check("data_unavailable_health_red", resp2.system_health.overall.value == "RED")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
