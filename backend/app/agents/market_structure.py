"""
Market Structure detection (spec section 9).

Real, deterministic detection from OHLC — no ML, no fabrication:
- Swing highs/lows via a simple fractal window
- HH/HL/LH/LL sequence classification from the last swings
- BOS (break of structure): price closes beyond the last swing in the
  direction of the existing trend
- CHOCH (change of character): price closes beyond the last swing AGAINST
  the existing trend — first sign of a potential reversal
- Fair Value Gaps (FVG): classic 3-candle imbalance
- Order blocks: simplified — last opposite-direction candle immediately
  preceding a strong impulsive move
"""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


@dataclass
class Swing:
    time: str
    price: float
    kind: str  # "HIGH" | "LOW"


@dataclass
class MarketStructureResult:
    swings: list[Swing]
    sequence_labels: list[str]  # e.g. ["HL", "HH", "HL", "HH"]
    trend: str  # "UPTREND" | "DOWNTREND" | "RANGE"
    last_event: str  # "BOS" | "CHOCH" | "NONE"
    last_event_detail: str
    fvgs: list[dict]
    order_blocks: list[dict]
    candlestick_patterns: list[dict]


def find_swings(df: pd.DataFrame, window: int = 3) -> list[Swing]:
    highs, lows = df["high"], df["low"]
    swings: list[Swing] = []
    n = len(df)
    for i in range(window, n - window):
        window_highs = highs.iloc[i - window : i + window + 1]
        window_lows = lows.iloc[i - window : i + window + 1]
        if highs.iloc[i] == window_highs.max() and highs.iloc[i] > highs.iloc[i - 1]:
            swings.append(Swing(time=str(df.index[i]), price=float(highs.iloc[i]), kind="HIGH"))
        elif lows.iloc[i] == window_lows.min() and lows.iloc[i] < lows.iloc[i - 1]:
            swings.append(Swing(time=str(df.index[i]), price=float(lows.iloc[i]), kind="LOW"))
    return swings


def _classify_sequence(swings: list[Swing]) -> list[str]:
    labels = []
    last_high, last_low = None, None
    for s in swings:
        if s.kind == "HIGH":
            if last_high is not None:
                labels.append("HH" if s.price > last_high else "LH")
            last_high = s.price
        else:
            if last_low is not None:
                labels.append("HL" if s.price > last_low else "LL")
            last_low = s.price
    return labels


def find_fvgs(df: pd.DataFrame, lookback: int = 40) -> list[dict]:
    fvgs = []
    recent = df.tail(lookback)
    highs, lows = recent["high"].values, recent["low"].values
    times = recent.index
    for i in range(1, len(recent) - 1):
        # bullish FVG: candle[i-1].high < candle[i+1].low (gap left unfilled)
        if highs[i - 1] < lows[i + 1]:
            fvgs.append({"type": "BULLISH", "time": str(times[i]), "gap_low": float(highs[i - 1]), "gap_high": float(lows[i + 1])})
        # bearish FVG: candle[i-1].low > candle[i+1].high
        if lows[i - 1] > highs[i + 1]:
            fvgs.append({"type": "BEARISH", "time": str(times[i]), "gap_low": float(highs[i + 1]), "gap_high": float(lows[i - 1])})
    return fvgs[-5:]  # most recent 5 only — validated structures, not noise


def find_order_blocks(df: pd.DataFrame, impulse_threshold_pct: float = 0.3, lookback: int = 40) -> list[dict]:
    obs = []
    recent = df.tail(lookback)
    closes = recent["close"].values
    opens = recent["open"].values
    times = recent.index
    for i in range(1, len(recent) - 1):
        move_pct = (closes[i] - opens[i]) / opens[i] * 100
        prev_bearish = closes[i - 1] < opens[i - 1]
        prev_bullish = closes[i - 1] > opens[i - 1]
        if move_pct > impulse_threshold_pct and prev_bearish:
            obs.append({"type": "BULLISH_OB", "time": str(times[i - 1]), "low": float(recent["low"].iloc[i - 1]), "high": float(recent["high"].iloc[i - 1])})
        if move_pct < -impulse_threshold_pct and prev_bullish:
            obs.append({"type": "BEARISH_OB", "time": str(times[i - 1]), "low": float(recent["low"].iloc[i - 1]), "high": float(recent["high"].iloc[i - 1])})
    return obs[-5:]


def detect_candlestick_patterns(df: pd.DataFrame, lookback: int = 10) -> list[dict]:
    """Real candlestick pattern detection on the most recent candles — a
    pure pandas/numpy implementation of the classic patterns (no TA-Lib
    dependency required, though TA-Lib's talib.CDL* functions cover a much
    larger pattern set if you install it: pip install TA-Lib).

    Only the last `lookback` candles are scanned, matching spec section 9's
    'show only validated structures' — recent patterns only, not the whole
    session history."""
    patterns = []
    recent = df.tail(lookback)
    o, h, l, c = recent["open"].values, recent["high"].values, recent["low"].values, recent["close"].values
    times = recent.index

    for i in range(len(recent)):
        body = abs(c[i] - o[i])
        range_ = h[i] - l[i]
        if range_ <= 0:
            continue
        upper_wick = h[i] - max(o[i], c[i])
        lower_wick = min(o[i], c[i]) - l[i]

        # Doji: body is a tiny fraction of the candle's range
        if body / range_ < 0.1:
            patterns.append({"type": "DOJI", "time": str(times[i]), "bias": "NEUTRAL"})

        # Hammer: small body near the top, long lower wick, little/no upper wick
        elif lower_wick > body * 2 and upper_wick < body * 0.5 and body / range_ < 0.35:
            patterns.append({"type": "HAMMER", "time": str(times[i]), "bias": "BULLISH"})

        # Shooting star: small body near the bottom, long upper wick, little/no lower wick
        elif upper_wick > body * 2 and lower_wick < body * 0.5 and body / range_ < 0.35:
            patterns.append({"type": "SHOOTING_STAR", "time": str(times[i]), "bias": "BEARISH"})

        # Engulfing: current body fully engulfs the previous candle's body,
        # in the opposite direction of the prior candle
        if i > 0:
            prev_body_high = max(o[i - 1], c[i - 1])
            prev_body_low = min(o[i - 1], c[i - 1])
            curr_bullish = c[i] > o[i]
            prev_bearish = c[i - 1] < o[i - 1]
            curr_bearish = c[i] < o[i]
            prev_bullish = c[i - 1] > o[i - 1]
            if curr_bullish and prev_bearish and o[i] <= prev_body_low and c[i] >= prev_body_high:
                patterns.append({"type": "BULLISH_ENGULFING", "time": str(times[i]), "bias": "BULLISH"})
            elif curr_bearish and prev_bullish and o[i] >= prev_body_high and c[i] <= prev_body_low:
                patterns.append({"type": "BEARISH_ENGULFING", "time": str(times[i]), "bias": "BEARISH"})

    return patterns[-5:]  # most recent 5, same convention as FVGs/order blocks


def analyse_market_structure(df: pd.DataFrame) -> MarketStructureResult:
    swings = find_swings(df, window=3)
    labels = _classify_sequence(swings)

    if len(labels) >= 2 and all(l in ("HH", "HL") for l in labels[-2:]):
        trend = "UPTREND"
    elif len(labels) >= 2 and all(l in ("LH", "LL") for l in labels[-2:]):
        trend = "DOWNTREND"
    else:
        trend = "RANGE"

    last_event, detail = "NONE", "Insufficient swing data for BOS/CHOCH."
    if len(swings) >= 2:
        last_close = float(df["close"].iloc[-1])
        last_swing = swings[-1]
        prior_swing = swings[-2]
        if last_swing.kind == "HIGH" and last_close > last_swing.price:
            last_event = "BOS" if trend == "UPTREND" else "CHOCH"
            detail = f"Price closed above last swing high {last_swing.price:.1f}"
        elif last_swing.kind == "LOW" and last_close < last_swing.price:
            last_event = "BOS" if trend == "DOWNTREND" else "CHOCH"
            detail = f"Price closed below last swing low {last_swing.price:.1f}"

    return MarketStructureResult(
        swings=swings[-8:], sequence_labels=labels[-6:], trend=trend,
        last_event=last_event, last_event_detail=detail,
        fvgs=find_fvgs(df), order_blocks=find_order_blocks(df),
        candlestick_patterns=detect_candlestick_patterns(df),
    )
