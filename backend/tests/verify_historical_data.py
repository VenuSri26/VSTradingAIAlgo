import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import historical_data as hd

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1; print(f"PASS  {name}")
    else:
        failed += 1; print(f"FAIL  {name}")

# In this offline sandbox nsepython isn't installed and there's no network,
# so these tests validate the FALLBACK CONTRACT: never crash, never
# fabricate a price series, always fail loud/quiet-None per the project's
# "never fabricate" rule. On a machine with nsepython + network installed,
# fetch_nifty_history() would additionally need a live-data integration
# test, which isn't possible here.

check("reports_unavailable_correctly", hd.nsepython_available() is False)

try:
    hd.fetch_nifty_history("01-01-2026", "05-01-2026")
    check("raises_when_nsepython_missing", False)
except hd.HistoricalDataUnavailable as e:
    check("raises_when_nsepython_missing", "nsepython not installed" in str(e))

lookup = hd.make_price_lookup_for_backtest()
result = lookup("2026-01-15T10:00:00+00:00", {"ltp": 100})
check("lookup_returns_none_not_crash", result is None)

# malformed timestamp must not crash the lookup either
result2 = lookup("not-a-real-timestamp", {"ltp": 100})
check("malformed_timestamp_handled", result2 is None)

# missing ltp in plan must not crash
result3 = lookup("2026-01-15T10:00:00+00:00", {})
check("missing_plan_fields_handled", result3 is None)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
