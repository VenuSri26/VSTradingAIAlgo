"""V7 real-time read model backed by KiteTicker ticks and verified Zerodha OHLC."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
import math

import pandas as pd

from app.features import build_features
from app.futures_volume import (
    build_futures_volume_snapshot,
    load_nifty_futures_ohlc,
    merge_futures_volume_into_indicators,
)
from app.live_market_stream import get_live_market_stream


def _json_safe(value: Any) -> Any:
    """Recursively convert NaN/Inf/numpy-like values into JSON-safe values."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]

    # Handles Python float plus numpy floating values convertible to float.
    try:
        if not isinstance(value, (str, bytes, bool, int)) and hasattr(value, "item"):
            value = value.item()
    except Exception:
        pass

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    return value


class LiveMarketRealtime:
    def __init__(self, data_source: Any, runtime: Any):
        self.data_source = data_source
        self.runtime = runtime
        self.stream = get_live_market_stream()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def feed(self) -> dict[str, Any]:
        runtime = self.runtime.status()
        stream = self.stream.status()
        return {
            "transport": runtime.get("transport"),
            "connected": bool(runtime.get("connected")),
            "running": bool(runtime.get("running")),
            "subscription_count": int(runtime.get("subscription_count") or 0),
            "last_tick_at": stream.get("last_tick_at") or runtime.get("last_tick_at"),
            "feed_age_sec": stream.get("age_sec"),
            "nifty_spot": stream.get("nifty_spot"),
            "india_vix": stream.get("india_vix"),
            "accepted_ticks": stream.get("accepted_ticks"),
            "ignored_ticks": stream.get("ignored_ticks"),
            "candle_counts": stream.get("candle_counts"),
            "live_orders_enabled": False,
            "generated_at": self._now(),
        }

    def ticks(self, *, limit: int = 100, instrument_token: int | None = None) -> dict[str, Any]:
        return {
            "items": self.stream.history(limit=limit, instrument_token=instrument_token),
            "feed": self.feed(),
            "live_orders_enabled": False,
        }

    def candles(self, *, timeframe: str = "3m", limit: int = 120, include_current: bool = True) -> dict[str, Any]:
        return {
            "timeframe": timeframe,
            "candles": self.stream.candles(timeframe=timeframe, limit=limit, include_current=include_current),
            "source": "KITE_TICKER_STREAM",
            "include_current": include_current,
            "live_orders_enabled": False,
        }

    @staticmethod
    def _rows_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime(df["start"], utc=True)
        return df[["open", "high", "low", "close", "volume"]].astype(float)

    def indicators(self, *, lookback: int = 120) -> dict[str, Any]:
        warnings: list[str] = []
        source = "KITE_TICKER_STREAM"
        # Exclude the forming 3-minute candle to avoid lookahead.
        streamed = self.stream.candles(timeframe="3m", limit=lookback, include_current=False)
        intraday = self._rows_to_df(streamed)
        if len(intraday) < 50:
            source = "ZERODHA_COMPLETED_OHLC"
            warnings.append("STREAM_WARMUP_USING_COMPLETED_ZERODHA_OHLC")
            intraday = self.data_source.get_ohlc("3m", max(60, lookback))
        daily = self.data_source.get_ohlc("1d", 5)
        if len(intraday) < 20 or len(daily) < 1:
            return {
                "status": "NOT_AVAILABLE",
                "source": source,
                "warnings": warnings + ["INSUFFICIENT_COMPLETED_CANDLES"],
                "indicators": None,
                "live_orders_enabled": False,
            }
        result = _json_safe(asdict(build_features(intraday, daily)))

        # V7.2: enrich NIFTY spot indicators with genuine NIFTY Futures
        # volume/VWAP intelligence. Failure here must never break the
        # existing V7.1 indicator path.
        try:
            futures_df, futures_meta = load_nifty_futures_ohlc(
                self.data_source,
                timeframe="3m",
                lookback=max(60, lookback),
            )

            spot_close = result.get("close")

            futures_snapshot = build_futures_volume_snapshot(
                futures_df,
                spot_close=spot_close,
            )

            if futures_snapshot.get("status") == "READY":
                result = merge_futures_volume_into_indicators(
                    result,
                    futures_snapshot,
                    futures_meta,
                )
            else:
                warnings.append("FUTURES_VOLUME_NOT_READY")

        except Exception:
            # Fail-open for analytics only. Existing spot intelligence
            # continues unchanged; no broker orders are ever enabled here.
            warnings.append("FUTURES_VOLUME_UNAVAILABLE")

        return {
            "status": "READY",
            "source": source,
            "completed_candles": len(intraday),
            "indicators": result,
            "warnings": warnings,
            "live_orders_enabled": False,
            "generated_at": self._now(),
        }
