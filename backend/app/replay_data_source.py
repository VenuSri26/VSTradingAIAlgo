from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

import pandas as pd

from app.data_sources.base import DataUnavailable


IST = "Asia/Kolkata"
UTC = "UTC"


def _utc_timestamp(value: datetime | str | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)

    if ts.tzinfo is None:
        ts = ts.tz_localize(IST)

    return ts.tz_convert(UTC)


def _normalise_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()

    out = frame.copy()

    if not isinstance(out.index, pd.DatetimeIndex):
        if "date" not in out.columns:
            raise ValueError(
                "Replay frame requires DatetimeIndex or a 'date' column"
            )

        out["date"] = pd.to_datetime(out["date"])
        out = out.set_index("date")

    idx = pd.DatetimeIndex(out.index)

    if idx.tz is None:
        idx = idx.tz_localize(IST)

    out.index = idx.tz_convert(UTC)

    return out.sort_index()


def _timeframe_delta(timeframe: str) -> pd.Timedelta:
    mapping = {
        "1m": pd.Timedelta(minutes=1),
        "3m": pd.Timedelta(minutes=3),
        "5m": pd.Timedelta(minutes=5),
        "15m": pd.Timedelta(minutes=15),
        "30m": pd.Timedelta(minutes=30),
        "60m": pd.Timedelta(hours=1),
        "1h": pd.Timedelta(hours=1),
    }

    try:
        return mapping[timeframe]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported replay timeframe: {timeframe}"
        ) from exc


class PointInTimeReplayDataSource:
    """
    Deterministic historical data source.

    Core safety rule:
    a candle becomes visible only after that candle has completed.

    Example for a 3-minute chart:
        replay clock 10:02 -> latest visible candle starts 09:57
        replay clock 10:03 -> latest visible candle starts 10:00

    Daily candles from the replay trading day are intentionally excluded
    because their final OHLC values would contain future information.
    """

    source = "HISTORICAL_POINT_IN_TIME_REPLAY"

    def __init__(
        self,
        *,
        spot_frames: dict[str, pd.DataFrame],
        as_of: datetime | str | pd.Timestamp,
        futures_frames: dict[str, pd.DataFrame] | None = None,
        vix: pd.Series | pd.DataFrame | None = None,
        option_snapshots: list[
            tuple[datetime | str | pd.Timestamp, dict[str, Any]]
        ] | None = None,
    ) -> None:
        self._spot_frames = {
            tf: _normalise_frame(df)
            for tf, df in spot_frames.items()
        }

        self._futures_frames = {
            tf: _normalise_frame(df)
            for tf, df in (futures_frames or {}).items()
        }

        self._vix = self._normalise_vix(vix)

        self._option_snapshots = sorted(
            [
                (_utc_timestamp(ts), deepcopy(snapshot))
                for ts, snapshot in (option_snapshots or [])
            ],
            key=lambda item: item[0],
        )

        self._as_of = _utc_timestamp(as_of)

    @staticmethod
    def _normalise_vix(
        value: pd.Series | pd.DataFrame | None,
    ) -> pd.Series | None:
        if value is None:
            return None

        if isinstance(value, pd.DataFrame):
            if value.empty:
                return pd.Series(dtype=float)

            for candidate in ("close", "vix", "value"):
                if candidate in value.columns:
                    series = value[candidate].copy()
                    break
            else:
                raise ValueError(
                    "VIX dataframe needs close/vix/value column"
                )
        else:
            series = value.copy()

        idx = pd.DatetimeIndex(pd.to_datetime(series.index))

        if idx.tz is None:
            idx = idx.tz_localize(IST)

        series.index = idx.tz_convert(UTC)

        return series.sort_index()

    @property
    def as_of(self) -> datetime:
        return self._as_of.to_pydatetime()

    def set_as_of(
        self,
        value: datetime | str | pd.Timestamp,
    ) -> None:
        self._as_of = _utc_timestamp(value)

    def is_connected(self) -> bool:
        # Replay data is local/preloaded, not a live broker connection.
        return True

    def _completed_slice(
        self,
        frame: pd.DataFrame,
        timeframe: str,
    ) -> pd.DataFrame:
        if frame.empty:
            return frame

        if timeframe == "1d":
            # Never expose today's final daily OHLC during an intraday replay.
            replay_day = self._as_of.tz_convert(IST).date()

            local_index = frame.index.tz_convert(IST)

            mask = [
                ts.date() < replay_day
                for ts in local_index
            ]

            return frame.loc[mask]

        completed_before = (
            self._as_of - _timeframe_delta(timeframe)
        )

        return frame.loc[
            frame.index <= completed_before
        ]

    def get_ohlc(
        self,
        timeframe: str,
        lookback: int,
    ) -> pd.DataFrame:
        frame = self._spot_frames.get(timeframe)

        if frame is None:
            raise DataUnavailable(
                f"Replay spot timeframe unavailable: {timeframe}"
            )

        visible = self._completed_slice(
            frame,
            timeframe,
        )

        if visible.empty:
            raise DataUnavailable(
                f"No completed {timeframe} spot candles at "
                f"{self._as_of.isoformat()}"
            )

        return visible.tail(lookback).copy()

    def get_futures_ohlc(
        self,
        timeframe: str,
        lookback: int,
    ) -> pd.DataFrame:
        frame = self._futures_frames.get(timeframe)

        if frame is None:
            raise DataUnavailable(
                f"Replay futures timeframe unavailable: {timeframe}"
            )

        visible = self._completed_slice(
            frame,
            timeframe,
        )

        if visible.empty:
            raise DataUnavailable(
                f"No completed {timeframe} futures candles at "
                f"{self._as_of.isoformat()}"
            )

        return visible.tail(lookback).copy()

    def get_spot(self) -> float:
        frame = self.get_ohlc("3m", 1)
        return float(frame["close"].iloc[-1])

    def get_last_tick_timestamp(self) -> str:
        frame = self.get_ohlc("3m", 1)
        return pd.Timestamp(frame.index[-1]).isoformat()

    def get_vix(self) -> float:
        if self._vix is None or self._vix.empty:
            raise DataUnavailable(
                "Historical VIX not supplied to replay"
            )

        visible = self._vix.loc[
            self._vix.index <= self._as_of
        ]

        if visible.empty:
            raise DataUnavailable(
                "No historical VIX available at replay timestamp"
            )

        return float(visible.iloc[-1])

    def get_option_chain(
        self,
        atm_range: int = 5,
    ) -> dict[str, Any]:
        del atm_range

        eligible = [
            snapshot
            for ts, snapshot in self._option_snapshots
            if ts <= self._as_of
        ]

        if not eligible:
            raise DataUnavailable(
                "Historical option snapshot unavailable "
                "at replay timestamp"
            )

        return deepcopy(eligible[-1])
