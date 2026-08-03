import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
from app.agents.market_structure import detect_candlestick_patterns

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1; print(f"PASS  {name}")
    else:
        failed += 1; print(f"FAIL  {name}")

def make_df(candles):
    """candles: list of (open, high, low, close) tuples"""
    return pd.DataFrame(candles, columns=["open", "high", "low", "close"],
                         index=pd.date_range("2026-01-01", periods=len(candles), freq="3min"))

# Doji: open ~= close, small body relative to range
df_doji = make_df([(100, 105, 95, 100.2)])
patterns = detect_candlestick_patterns(df_doji)
check("doji_detected", any(p["type"] == "DOJI" for p in patterns))

# Hammer: small-ish body near top, long lower wick, minimal upper wick
df_hammer = make_df([(100, 101.6, 90, 101.5)])
patterns = detect_candlestick_patterns(df_hammer)
check("hammer_detected", any(p["type"] == "HAMMER" and p["bias"] == "BULLISH" for p in patterns))

# Shooting star: small-ish body near bottom, long upper wick, minimal lower wick
df_star = make_df([(100, 110, 98.3, 98.5)])
patterns = detect_candlestick_patterns(df_star)
check("shooting_star_detected", any(p["type"] == "SHOOTING_STAR" and p["bias"] == "BEARISH" for p in patterns))

# Bullish engulfing: prior red candle, current green candle fully engulfs it
df_bull_engulf = make_df([
    (105, 106, 99, 100),   # bearish candle: open 105 -> close 100
    (99, 107, 98, 106),    # bullish candle engulfing: open 99 -> close 106
])
patterns = detect_candlestick_patterns(df_bull_engulf)
check("bullish_engulfing_detected", any(p["type"] == "BULLISH_ENGULFING" for p in patterns))

# Bearish engulfing: prior green candle, current red candle fully engulfs it
df_bear_engulf = make_df([
    (100, 106, 99, 105),   # bullish candle: open 100 -> close 105
    (106, 107, 98, 99),    # bearish candle engulfing: open 106 -> close 99
])
patterns = detect_candlestick_patterns(df_bear_engulf)
check("bearish_engulfing_detected", any(p["type"] == "BEARISH_ENGULFING" for p in patterns))

# A plain, unremarkable candle should NOT trigger any pattern
df_plain = make_df([(100, 108, 92, 106)])  # big body, roughly even wicks
patterns = detect_candlestick_patterns(df_plain)
check("plain_candle_no_false_positive", len(patterns) == 0)

# only the most recent 5 patterns are returned, per the FVG/order-block convention
many_dojis = make_df([(100, 105, 95, 100.1)] * 10)
patterns = detect_candlestick_patterns(many_dojis)
check("limited_to_5_most_recent", len(patterns) <= 5)

# zero-range candle (open==high==low==close) must not crash
df_flat = make_df([(100, 100, 100, 100)])
try:
    detect_candlestick_patterns(df_flat)
    check("zero_range_candle_no_crash", True)
except ZeroDivisionError:
    check("zero_range_candle_no_crash", False)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
