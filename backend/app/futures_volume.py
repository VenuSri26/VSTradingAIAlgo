from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd


INTERVAL_MAP = {
    "1m": ("minute", 1),
    "3m": ("3minute", 3),
    "5m": ("5minute", 5),
    "15m": ("15minute", 15),
    "1d": ("day", 1440),
}


def _expiry_date(value: Any) -> date | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:
        return pd.Timestamp(value).date()
    except Exception:
        return None


def select_nearest_nifty_future(
    instruments: list[dict[str, Any]],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Return the nearest non-expired NIFTY futures contract."""

    today = today or datetime.now(timezone.utc).date()

    candidates: list[tuple[date, dict[str, Any]]] = []

    for item in instruments:
        name = str(item.get("name") or "").upper()
        symbol = str(item.get("tradingsymbol") or "").upper()
        segment = str(item.get("segment") or "").upper()
        instrument_type = str(item.get("instrument_type") or "").upper()

        is_nifty = name == "NIFTY" or symbol.startswith("NIFTY")
        is_future = (
            instrument_type == "FUT"
            or segment == "NFO-FUT"
            or symbol.endswith("FUT")
        )

        if not (is_nifty and is_future):
            continue

        expiry = _expiry_date(item.get("expiry"))

        if expiry is None or expiry < today:
            continue

        candidates.append((expiry, item))

    if not candidates:
        raise ValueError("No active NIFTY futures contract found")

    candidates.sort(key=lambda x: x[0])

    return candidates[0][1]


def _drop_forming_candle(
    df: pd.DataFrame,
    timeframe: str,
) -> pd.DataFrame:
    if df.empty or timeframe == "1d":
        return df

    if timeframe not in INTERVAL_MAP:
        return df

    minutes = INTERVAL_MAP[timeframe][1]

    try:
        last_ts = pd.Timestamp(df.index[-1])

        if last_ts.tzinfo is None:
            last_ts = last_ts.tz_localize("Asia/Kolkata")

        now = pd.Timestamp.now(tz=last_ts.tz)

        candle_end = last_ts + pd.Timedelta(minutes=minutes)

        if now < candle_end:
            return df.iloc[:-1]
    except Exception:
        pass

    return df


def load_nifty_futures_ohlc(
    data_source: Any,
    *,
    timeframe: str = "3m",
    lookback: int = 120,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Fetch completed OHLCV candles from the nearest NIFTY futures contract.

    This is market-data only. It never sends orders.
    """

    if timeframe not in INTERVAL_MAP:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    if lookback <= 0:
        raise ValueError("lookback must be positive")

    if hasattr(data_source, "is_connected") and not data_source.is_connected():
        raise RuntimeError("Zerodha session not authenticated")

    instruments = data_source._get_nfo_instruments()

    contract = select_nearest_nifty_future(instruments)

    token = int(contract["instrument_token"])

    interval, minutes = INTERVAL_MAP[timeframe]

    now = datetime.now(timezone.utc)

    # Large enough window to cover weekends/holidays safely.
    from_date = now - pd.Timedelta(
        minutes=max(lookback * minutes * 3, 3 * 1440)
    )

    candles = data_source._kite.historical_data(
        token,
        from_date,
        now,
        interval,
    )

    if not candles:
        raise RuntimeError("Zerodha returned no NIFTY futures candles")

    df = pd.DataFrame(candles).rename(columns=str.lower)

    required = {"date", "open", "high", "low", "close", "volume"}

    missing = required.difference(df.columns)

    if missing:
        raise RuntimeError(
            f"NIFTY futures candles missing columns: {sorted(missing)}"
        )

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])

    df = _drop_forming_candle(df, timeframe)

    df = df.tail(lookback)

    meta = {
        "tradingsymbol": contract.get("tradingsymbol"),
        "instrument_token": token,
        "expiry": str(contract.get("expiry")),
        "timeframe": timeframe,
        "candles": len(df),
        "source": "ZERODHA_NIFTY_FUTURES",
    }

    return df[
        ["open", "high", "low", "close", "volume"]
    ], meta


def build_futures_volume_snapshot(
    candles: pd.DataFrame,
    *,
    spot_close: float | None = None,
    relative_volume_window: int = 20,
) -> dict[str, Any]:
    """
    Compute volume intelligence from completed NIFTY futures candles.

    VWAP is calculated from actual NIFTY futures volume.
    """

    if candles is None or candles.empty:
        return {
            "status": "NOT_AVAILABLE",
            "reason": "NO_FUTURES_CANDLES",
        }

    df = candles.copy()

    required = {"high", "low", "close", "volume"}

    if not required.issubset(df.columns):
        return {
            "status": "NOT_AVAILABLE",
            "reason": "INVALID_FUTURES_CANDLES",
        }

    for col in ["high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["high", "low", "close", "volume"])

    if df.empty:
        return {
            "status": "NOT_AVAILABLE",
            "reason": "NO_VALID_FUTURES_CANDLES",
        }

    # Restrict VWAP to the latest trading session.
    try:
        latest_day = pd.Timestamp(df.index[-1]).date()
        session = df[
            pd.Index(
                [pd.Timestamp(x).date() for x in df.index]
            ) == latest_day
        ].copy()
    except Exception:
        session = df.copy()

    if session.empty:
        session = df.copy()

    volume = session["volume"].clip(lower=0)

    typical_price = (
        session["high"]
        + session["low"]
        + session["close"]
    ) / 3.0

    total_volume = float(volume.sum())

    futures_vwap: float | None = None

    if total_volume > 0:
        futures_vwap = float(
            (typical_price * volume).sum()
            / total_volume
        )

    futures_close = float(session["close"].iloc[-1])
    last_volume = float(volume.iloc[-1])

    previous = volume.iloc[
        max(0, len(volume) - relative_volume_window - 1):-1
    ]

    if previous.empty:
        previous = volume.iloc[:-1]

    avg_volume = (
        float(previous.mean())
        if len(previous) and float(previous.mean()) > 0
        else 0.0
    )

    relative_volume = (
        float(last_volume / avg_volume)
        if avg_volume > 0
        else 0.0
    )

    basis: float | None = None
    spot_equivalent_vwap: float | None = None

    if spot_close is not None:
        try:
            spot = float(spot_close)
            basis = futures_close - spot

            if futures_vwap is not None:
                spot_equivalent_vwap = futures_vwap - basis
        except Exception:
            pass

    volume_confirmed = bool(
        total_volume > 0
        and relative_volume >= 1.20
    )

    return {
        "status": "READY",
        "futures_close": futures_close,
        "futures_vwap": futures_vwap,
        "spot_equivalent_vwap": spot_equivalent_vwap,
        "basis": basis,
        "last_volume": last_volume,
        "avg_volume": avg_volume,
        "relative_volume": relative_volume,
        "session_volume": total_volume,
        "session_candles": int(len(session)),
        "volume_confirmed": volume_confirmed,
        "relative_volume_threshold": 1.20,
        "source": "ZERODHA_NIFTY_FUTURES",
    }


def merge_futures_volume_into_indicators(
    indicators: dict[str, Any],
    futures_snapshot: dict[str, Any],
    futures_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Enrich existing NIFTY spot indicators with NIFTY Futures volume intelligence.

    Existing spot indicators remain the primary technical-analysis source.
    Futures are used only for volume/VWAP/participation intelligence.
    """
    result = dict(indicators or {})
    snap = dict(futures_snapshot or {})
    meta = dict(futures_meta or {})

    if snap.get("status") != "READY":
        return result

    # Spot-equivalent futures VWAP lets existing consumers continue reading
    # the normal vwap field without comparing spot against raw futures basis.
    spot_vwap = snap.get("spot_equivalent_vwap")

    if spot_vwap is not None:
        result["vwap"] = spot_vwap

    result["volume"] = snap.get("last_volume")
    result["avg_volume"] = snap.get("avg_volume")
    result["relative_volume"] = snap.get("relative_volume")

    result["futures_close"] = snap.get("futures_close")
    result["futures_vwap"] = snap.get("futures_vwap")
    result["futures_basis"] = snap.get("basis")
    result["futures_session_volume"] = snap.get("session_volume")
    result["volume_confirmed"] = bool(snap.get("volume_confirmed"))

    result["futures_symbol"] = meta.get("tradingsymbol")
    result["futures_expiry"] = meta.get("expiry")
    result["volume_source"] = snap.get(
        "source",
        "ZERODHA_NIFTY_FUTURES",
    )

    return result


def merge_futures_volume_into_features(
    features: Any,
    futures_snapshot: dict[str, Any],
) -> Any:
    """
    V7.2 decision-pipeline enrichment.

    NIFTY spot remains authoritative for:
    close, EMA, RSI, MACD, ADX, ATR and price levels.

    NIFTY Futures provides:
    VWAP, real traded volume, average volume and relative volume.

    If Futures intelligence is unavailable, the original Features
    object is returned unchanged.
    """
    from dataclasses import replace
    import math

    snap = dict(futures_snapshot or {})

    if snap.get("status") != "READY":
        return features

    values = {
        "vwap": snap.get("spot_equivalent_vwap"),
        "volume": snap.get("last_volume"),
        "avg_volume": snap.get("avg_volume"),
        "relative_volume": snap.get("relative_volume"),
    }

    clean = {}

    for key, value in values.items():
        if value is None:
            continue

        try:
            value = float(value)
        except (TypeError, ValueError):
            continue

        if math.isfinite(value):
            clean[key] = value

    if not clean:
        return features

    return replace(features, **clean)
