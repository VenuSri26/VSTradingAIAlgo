"""Thread-safe real-time market cache for V7.

This module stores only broker ticks received through the KiteTicker runtime.
It never generates synthetic prices. It also builds small in-memory OHLC series
for NIFTY from accepted ticks; when a historical indicator is requested and
there are not enough streamed candles yet, callers may explicitly fall back to
completed Zerodha historical candles.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any

import pandas as pd

from app.data_sources.zerodha_client import INDIA_VIX_TOKEN, NIFTY_INSTRUMENT_TOKEN


@dataclass
class StreamCandle:
    start: str
    end: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    ticks: int = 0


class _CandleSeries:
    def __init__(self, minutes: int, max_items: int = 600):
        self.minutes = minutes
        self.completed: deque[StreamCandle] = deque(maxlen=max_items)
        self.current: StreamCandle | None = None

    def _bucket(self, ts: datetime) -> tuple[datetime, datetime]:
        ts = ts.astimezone(timezone.utc).replace(second=0, microsecond=0)
        minute = ts.minute - (ts.minute % self.minutes)
        start = ts.replace(minute=minute)
        return start, start + pd.Timedelta(minutes=self.minutes)

    def add(self, price: float, ts: datetime, volume_delta: float = 0.0) -> None:
        start, end = self._bucket(ts)
        key = start.isoformat()
        if self.current is None or self.current.start != key:
            if self.current is not None:
                self.completed.append(self.current)
            self.current = StreamCandle(
                start=key,
                end=end.isoformat(),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=max(0.0, float(volume_delta or 0.0)),
                ticks=1,
            )
            return
        self.current.high = max(self.current.high, price)
        self.current.low = min(self.current.low, price)
        self.current.close = price
        self.current.volume += max(0.0, float(volume_delta or 0.0))
        self.current.ticks += 1

    def rows(self, *, include_current: bool = True, limit: int = 200) -> list[dict[str, Any]]:
        rows = [asdict(x) for x in self.completed]
        if include_current and self.current is not None:
            rows.append(asdict(self.current))
        return rows[-max(1, limit):]


class LiveMarketStream:
    """Process-local cache fed exclusively from accepted broker ticks."""

    def __init__(self, history_size: int = 5000):
        self._lock = RLock()
        self._latest: dict[int, dict[str, Any]] = {}
        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._candles = {tf: _CandleSeries(m) for tf, m in (("1m", 1), ("3m", 3), ("5m", 5))}
        self._last_cumulative_volume: dict[int, float] = defaultdict(float)
        self._accepted = 0
        self._ignored = 0
        self._last_tick_at: str | None = None

    @staticmethod
    def _parse_ts(value: Any) -> datetime:
        if isinstance(value, datetime):
            dt = value
        elif value:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        else:
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def ingest(self, tick: dict[str, Any]) -> dict[str, Any]:
        token = int(tick.get("instrument_token") or 0)
        price = tick.get("ltp")
        if token <= 0 or price is None:
            with self._lock:
                self._ignored += 1
            return {"status": "IGNORED", "reason": "MISSING_TOKEN_OR_PRICE"}

        try:
            price_f = float(price)
            ts = self._parse_ts(tick.get("exchange_timestamp"))
        except (TypeError, ValueError):
            with self._lock:
                self._ignored += 1
            return {"status": "IGNORED", "reason": "INVALID_PRICE_OR_TIMESTAMP"}

        cumulative_volume = float(tick.get("volume") or 0.0)
        with self._lock:
            previous_volume = self._last_cumulative_volume[token]
            volume_delta = max(0.0, cumulative_volume - previous_volume) if cumulative_volume else 0.0
            if cumulative_volume:
                self._last_cumulative_volume[token] = cumulative_volume

            normalized = {
                **tick,
                "instrument_token": token,
                "ltp": price_f,
                "exchange_timestamp": ts.isoformat(),
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
            self._latest[token] = normalized
            self._history.append(normalized)
            self._accepted += 1
            self._last_tick_at = normalized["received_at"]

            if token == NIFTY_INSTRUMENT_TOKEN or str(tick.get("asset_type") or "").upper() == "NIFTY_INDEX":
                for series in self._candles.values():
                    series.add(price_f, ts, volume_delta)

        return {"status": "ACCEPTED", "instrument_token": token}

    def latest(self, token: int | None = None) -> dict[str, Any]:
        with self._lock:
            if token is not None:
                return dict(self._latest.get(int(token)) or {})
            return {str(k): dict(v) for k, v in self._latest.items()}

    def history(self, limit: int = 100, instrument_token: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._history)
        if instrument_token is not None:
            rows = [x for x in rows if int(x.get("instrument_token") or 0) == int(instrument_token)]
        return rows[-max(1, min(limit, 1000)):]

    def candles(self, timeframe: str = "3m", limit: int = 120, include_current: bool = True) -> list[dict[str, Any]]:
        if timeframe not in self._candles:
            raise ValueError("timeframe must be one of 1m, 3m, 5m")
        with self._lock:
            return self._candles[timeframe].rows(include_current=include_current, limit=limit)

    def status(self) -> dict[str, Any]:
        with self._lock:
            nifty = dict(self._latest.get(NIFTY_INSTRUMENT_TOKEN) or {})
            vix = dict(self._latest.get(INDIA_VIX_TOKEN) or {})
            latest_count = len(self._latest)
            accepted = self._accepted
            ignored = self._ignored
            last_tick = self._last_tick_at
            candle_counts = {tf: len(series.rows(limit=10000)) for tf, series in self._candles.items()}
        age_sec = None
        if last_tick:
            try:
                age_sec = max(0.0, (datetime.now(timezone.utc) - self._parse_ts(last_tick)).total_seconds())
            except ValueError:
                pass
        return {
            "latest_instruments": latest_count,
            "accepted_ticks": accepted,
            "ignored_ticks": ignored,
            "last_tick_at": last_tick,
            "age_sec": round(age_sec, 3) if age_sec is not None else None,
            "nifty_spot": nifty.get("ltp"),
            "india_vix": vix.get("ltp"),
            "candle_counts": candle_counts,
            "live_orders_enabled": False,
        }


_stream: LiveMarketStream | None = None


def get_live_market_stream() -> LiveMarketStream:
    global _stream
    if _stream is None:
        _stream = LiveMarketStream()
    return _stream
