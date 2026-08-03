"""
Feature engine — computes real indicator values from OHLC candles.

Every agent reads from a single Features object rather than recomputing
indicators itself, so numbers stay consistent across the dashboard (spec
section 8: "indicators must support agent reasoning, not independently
trigger trades").

NO LOOKAHEAD (section 38): callers must pass only completed candles. This
module does not fetch data itself — it is pure computation on what it's given.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)


def macd(series: pd.Series, fast=12, slow=26, signal=9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = atr(df, period)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / tr.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / tr.replace(0, np.nan)
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0.0)


def vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum()
    cum_pv = (typical * df["volume"]).cumsum()
    return cum_pv / cum_vol.replace(0, np.nan)


@dataclass
class Features:
    close: float
    ema20: float
    ema50: float
    rsi14: float
    macd_hist: float
    adx14: float
    atr14: float
    vwap: float
    volume: float
    avg_volume: float
    relative_volume: float
    day_open: float
    pdh: float
    pdl: float
    pdc: float
    session_high: float
    session_low: float


def build_features(df_3m: pd.DataFrame, df_1d: pd.DataFrame) -> Features:
    """df_3m: intraday 3-minute candles (today so far). df_1d: daily candles
    (needs >=2 rows for previous day high/low/close)."""
    close = df_3m["close"]
    e20 = ema(close, 20)
    e50 = ema(close, 50)
    r14 = rsi(close, 14)
    _, _, hist = macd(close)
    a14 = adx(df_3m, 14)
    tr14 = atr(df_3m, 14)
    vw = vwap(df_3m)

    prev_day = df_1d.iloc[-2] if len(df_1d) >= 2 else df_1d.iloc[-1]

    return Features(
        close=float(close.iloc[-1]),
        ema20=float(e20.iloc[-1]),
        ema50=float(e50.iloc[-1]),
        rsi14=float(r14.iloc[-1]),
        macd_hist=float(hist.iloc[-1]),
        adx14=float(a14.iloc[-1]),
        atr14=float(tr14.iloc[-1]),
        vwap=float(vw.iloc[-1]),
        volume=float(df_3m["volume"].iloc[-1]),
        avg_volume=float(df_3m["volume"].tail(20).mean()),
        relative_volume=float(df_3m["volume"].iloc[-1] / max(df_3m["volume"].tail(20).mean(), 1e-9)),
        day_open=float(df_3m["open"].iloc[0]),
        pdh=float(prev_day["high"]),
        pdl=float(prev_day["low"]),
        pdc=float(prev_day["close"]),
        session_high=float(df_3m["high"].max()),
        session_low=float(df_3m["low"].min()),
    )
