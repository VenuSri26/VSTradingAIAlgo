import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# isolate this test run to a scratch DB/log so it never touches real data
os.environ["SQLITE_DB_PATH"] = "/tmp/test_store_verify.db"
os.environ["AUDIT_LOG_PATH"] = "/tmp/test_store_verify_audit.jsonl"
for p in (os.environ["SQLITE_DB_PATH"], os.environ["AUDIT_LOG_PATH"]):
    if os.path.exists(p):
        os.remove(p)

from app import store
from app.analytics import todays_skip_and_block_counts

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1; print(f"PASS  {name}")
    else:
        failed += 1; print(f"FAIL  {name}")

# fresh session row
s = store.get_session_dict()
check("fresh_session_zeroed", s["trades_today"] == 0 and s["daily_pnl"] == 0)

# open a position
pos_id = store.open_position("CE", 25300, 75, 100.0, 85.0, 125.0, 145.0)
check("position_opens", pos_id is not None)

open_pos = store.get_open_position()
check("open_position_visible", open_pos is not None and open_pos["status"] == "OPEN")

# cannot double count: a second get_open_position call is idempotent
check("open_position_idempotent", store.get_open_position()["id"] == pos_id)

# close it at a profit: (120-100)*75 = 1500
closed = store.close_position(pos_id, 120.0, "CLOSED_TARGET")
check("close_price_recorded", closed["close_price"] == 120.0)
check("pnl_computed_correctly", abs(closed["pnl"] - 1500.0) < 0.01)

store.record_trade_result(closed["pnl"], "A+")
s2 = store.get_session_dict()
check("session_trades_incremented", s2["trades_today"] == 1)
check("session_wins_incremented", s2["wins"] == 1)
check("session_pnl_accumulated", abs(s2["daily_pnl"] - 1500.0) < 0.01)
check("session_a_plus_counted", s2["a_plus_trades"] == 1)

check("position_closed_no_longer_open", store.get_open_position() is None)

# a losing trade next
pos_id2 = store.open_position("PE", 25200, 75, 80.0, 68.0, 100.0, 116.0)
closed2 = store.close_position(pos_id2, 68.0, "CLOSED_SL")
store.record_trade_result(closed2["pnl"], "A")
s3 = store.get_session_dict()
check("consecutive_losses_after_loss", s3["consecutive_losses"] == 1)
check("wins_still_one", s3["wins"] == 1)
check("losses_now_one", s3["losses"] == 1)

# consecutive losses reset on a win
pos_id3 = store.open_position("CE", 25300, 75, 90.0, 76.0, 112.0, 130.0)
closed3 = store.close_position(pos_id3, 112.0, "CLOSED_TARGET")
store.record_trade_result(closed3["pnl"], "A")
s4 = store.get_session_dict()
check("consecutive_losses_reset_on_win", s4["consecutive_losses"] == 0)

# audit-log-derived skip/block counts
from app.audit_log import log_decision
from app.data_sources.mock_source import MockDataSource
from app.pipeline import run_pipeline
resp = run_pipeline(MockDataSource(seed=9))
log_decision(resp, outcome_status="SKIPPED")
log_decision(resp, outcome_status="BLOCKED")
log_decision(resp, outcome_status="BLOCKED")
skipped, blocked = todays_skip_and_block_counts()
check("skip_count_correct", skipped == 1)
check("block_count_correct", blocked == 2)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
