"""
MockDataSource — synthetic but internally-consistent Nifty50 candle series.

IMPORTANT: this is explicitly labelled Source.MOCK everywhere it surfaces
(see models.Source). It exists purely so the multi-agent pipeline can run,
be unit tested, and be demoed end-to-end without live Zerodha credentials.
It must NEVER be reachable when the system is configured for live trading
(app/config.py enforces this — TRADING_MODE=live refuses to boot with
MockDataSource selected).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from .base import DataSource


class MockDataSource(DataSource):
    def __init__(self, seed: int = 42, base_price: float = 25300.0):
        self._rng = np.random.default_rng(seed)
        self._base_price = base_price
        self._connected = True

    def is_connected(self) -> bool:
        return self._connected

    @property
    def source_name(self) -> str:
        return "MOCK"

    def _generate(self, n: int, freq_minutes: int) -> pd.DataFrame:
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        times = [now - timedelta(minutes=freq_minutes * i) for i in range(n)][::-1]
        # simple mean-reverting random walk with slight upward drift, so
        # indicator math (EMA/RSI/MACD/ADX/ATR/VWAP) has realistic structure
        returns = self._rng.normal(loc=0.0003, scale=0.0018, size=n)
        closes = self._base_price * np.cumprod(1 + returns)
        highs = closes * (1 + np.abs(self._rng.normal(0.0006, 0.0004, n)))
        lows = closes * (1 - np.abs(self._rng.normal(0.0006, 0.0004, n)))
        opens = np.roll(closes, 1)
        opens[0] = closes[0]
        volumes = self._rng.integers(80_000, 400_000, n)
        df = pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
            index=pd.DatetimeIndex(times, name="time"),
        )
        return df

    def get_ohlc(self, timeframe: str, lookback: int) -> pd.DataFrame:
        tf_minutes = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "1d": 1440}.get(timeframe, 3)
        return self._generate(lookback, tf_minutes)

    def get_spot(self) -> float:
        return float(self.get_ohlc("3m", 1)["close"].iloc[-1])

    def get_vix(self) -> float:
        return float(round(13 + self._rng.normal(0, 1.2), 2))

    def get_option_chain(self, atm_range: int = 5) -> dict:
        from datetime import datetime, timedelta, timezone
        spot = self.get_spot()
        atm = round(spot / 50) * 50
        strikes = [atm + i * 50 for i in range(-atm_range, atm_range + 1)]
        # nearest weekly expiry: NIFTY weekly options expire Tuesday as of
        # the 2025 NSE calendar change (was Thursday historically) — verify
        # the current weekday against NSE's live circular before trusting
        # this in production; here it's just enough to give Greeks a
        # realistic days-to-expiry input.
        today = datetime.now(timezone.utc)
        days_ahead = (1 - today.weekday()) % 7  # 1 = Tuesday
        days_ahead = 7 if days_ahead == 0 else days_ahead
        expiry = (today + timedelta(days=days_ahead)).date().isoformat()
        chain = {"CE": [], "PE": []}
        for k in strikes:
            dist = abs(k - spot)
            base_oi = int(max(50_000, 900_000 - dist * 2000))
            for side in ("CE", "PE"):
                itm = (k < spot) if side == "CE" else (k > spot)
                if itm:
                    # ITM price must be full intrinsic value plus a positive
                    # time-value premium — previously this used only 0.35x
                    # the intrinsic distance, which could price options
                    # below their own no-arbitrage floor (see
                    # tests/test_greeks.py for why that matters: it made
                    # Greeks correctly refuse to solve for many ITM legs).
                    intrinsic = abs(spot - k)
                    time_value = max(2.0, self._rng.normal(20, 8))
                    ltp = intrinsic + time_value
                else:
                    ltp = max(0.5, self._rng.normal(40, 20) - dist * 0.05)
                ltp = round(max(ltp, 0.5), 2)
                chain[side].append({
                    "strike": k,
                    "ltp": ltp,
                    "oi": base_oi + int(self._rng.integers(-20000, 20000)),
                    "oi_change": int(self._rng.integers(-50000, 50000)),
                    "volume": int(self._rng.integers(1000, 200000)),
                    "iv": round(11 + abs(self._rng.normal(2, 1.5)), 2),
                    "bid": round(max(ltp - 0.5, 0.05), 2),
                    "ask": round(ltp + 0.5, 2),
                })
        return {"atm": atm, "spot": spot, "chain": chain, "expiry": expiry}

    def get_last_tick_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()
