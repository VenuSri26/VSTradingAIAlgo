import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
from app.backtest import evaluate_trade, evaluate_audit_log, summarize

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1; print(f"PASS  {name}")
    else:
        failed += 1; print(f"FAIL  {name}")

plan = {"ltp": 100.0, "stop_loss": 85.0, "target_1": 125.0, "target_2": 145.0}

# Case 1: price rallies straight to T1
prices = pd.Series([105, 112, 120, 126, 130])
ev = evaluate_trade(plan, prices)
check("hits_t1_correctly", ev.outcome == "HIT_T1")
check("t1_rr_correct", ev.realized_rr == round((125 - 100) / (100 - 85), 2))
check("mfe_captures_peak_before_exit", ev.mfe == 26)  # 126-100

# Case 2: price drops straight to SL
prices2 = pd.Series([98, 92, 87, 84])
ev2 = evaluate_trade(plan, prices2)
check("hits_sl_correctly", ev2.outcome == "HIT_SL")
check("sl_rr_is_minus_one", ev2.realized_rr == -1.0)
check("mae_captures_worst_before_exit", ev2.mae == 16)  # 100-84

# Case 3: price never reaches SL or T1
prices3 = pd.Series([102, 98, 103, 99, 101])
ev3 = evaluate_trade(plan, prices3)
check("no_touch_when_neither_hit", ev3.outcome == "NO_TOUCH")
check("no_touch_rr_none", ev3.realized_rr is None)

# Case 4: gaps straight past both T1 and T2 in the very first tick
prices4 = pd.Series([150, 160])
ev4 = evaluate_trade(plan, prices4)
check("hits_t2_when_gapped_past_t1", ev4.outcome == "HIT_T2")

# Case 5: invalid plan (missing ltp) doesn't crash
bad_plan = {"ltp": None, "stop_loss": None, "target_1": None, "target_2": None}
ev5 = evaluate_trade(bad_plan, pd.Series([100, 101]))
check("invalid_plan_handled_gracefully", ev5.outcome == "INVALID")

# end-to-end: evaluate_audit_log + summarize
records = [
    {"timestamp": "t1", "outcome_status": "GENERATED", "decision": "CE_BUY", "grade": "A+", "plan": plan},
    {"timestamp": "t2", "outcome_status": "GENERATED", "decision": "CE_BUY", "grade": "A", "plan": plan},
    {"timestamp": "t3", "outcome_status": "SKIPPED", "decision": "NO_TRADE", "grade": "NO_TRADE", "plan": None},
]
def price_lookup(ts, plan):
    return prices if ts == "t1" else prices2  # t1 wins, t2 loses

evals = evaluate_audit_log(records, price_lookup)
check("skipped_records_excluded", len(evals) == 2)
summary = summarize(evals)
check("summary_win_rate_50pct", summary["win_rate"] == 50.0)
check("summary_by_grade_present", "A+" in summary["by_grade"] and "A" in summary["by_grade"])

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
