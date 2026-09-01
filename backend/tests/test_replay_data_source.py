from datetime import datetime

import pandas as pd

from app.replay_data_source import PointInTimeReplayDataSource


def _frame(times, closes, volumes=None):
    if volumes is None:
        volumes = [100] * len(times)

    return pd.DataFrame(
        {
            "open": closes,
            "high": [x + 1 for x in closes],
            "low": [x - 1 for x in closes],
            "close": closes,
            "volume": volumes,
        },
        index=pd.DatetimeIndex(times),
    )


def test_three_minute_replay_cannot_see_forming_or_future_candle():
    spot = _frame(
        [
            "2026-08-11 09:15",
            "2026-08-11 09:18",
            "2026-08-11 09:21",
            "2026-08-11 09:24",
        ],
        [100, 101, 102, 999],
    )

    ds = PointInTimeReplayDataSource(
        spot_frames={"3m": spot},
        as_of=datetime(2026, 8, 11, 9, 23),
    )

    visible = ds.get_ohlc("3m", 100)

    assert list(visible["close"]) == [100, 101]
    assert 102 not in visible["close"].tolist()
    assert 999 not in visible["close"].tolist()


def test_candle_becomes_visible_only_when_completed():
    spot = _frame(
        [
            "2026-08-11 09:15",
            "2026-08-11 09:18",
            "2026-08-11 09:21",
        ],
        [100, 101, 102],
    )

    ds = PointInTimeReplayDataSource(
        spot_frames={"3m": spot},
        as_of=datetime(2026, 8, 11, 9, 23),
    )

    assert ds.get_spot() == 101

    ds.set_as_of(
        datetime(2026, 8, 11, 9, 24)
    )

    assert ds.get_spot() == 102


def test_daily_replay_excludes_same_day_final_candle():
    daily = _frame(
        [
            "2026-08-07 09:15",
            "2026-08-10 09:15",
            "2026-08-11 09:15",
        ],
        [90, 95, 999],
    )

    ds = PointInTimeReplayDataSource(
        spot_frames={
            "1d": daily,
            "3m": _frame(
                ["2026-08-11 09:15"],
                [100],
            ),
        },
        as_of=datetime(2026, 8, 11, 12, 0),
    )

    visible = ds.get_ohlc("1d", 10)

    assert list(visible["close"]) == [90, 95]
    assert 999 not in visible["close"].tolist()


def test_futures_replay_has_same_no_lookahead_rule():
    spot = _frame(
        ["2026-08-11 09:15"],
        [100],
    )

    futures = _frame(
        [
            "2026-08-11 09:15",
            "2026-08-11 09:18",
            "2026-08-11 09:21",
        ],
        [110, 111, 999],
        [1000, 1200, 999999],
    )

    ds = PointInTimeReplayDataSource(
        spot_frames={"3m": spot},
        futures_frames={"3m": futures},
        as_of=datetime(2026, 8, 11, 9, 23),
    )

    visible = ds.get_futures_ohlc("3m", 100)

    assert list(visible["close"]) == [110, 111]
    assert 999 not in visible["close"].tolist()


def test_historical_vix_respects_replay_clock():
    spot = _frame(
        ["2026-08-11 09:15"],
        [100],
    )

    vix = pd.Series(
        [12.0, 13.0, 99.0],
        index=pd.DatetimeIndex(
            [
                "2026-08-11 09:15",
                "2026-08-11 09:18",
                "2026-08-11 09:30",
            ]
        ),
    )

    ds = PointInTimeReplayDataSource(
        spot_frames={"3m": spot},
        vix=vix,
        as_of=datetime(2026, 8, 11, 9, 20),
    )

    assert ds.get_vix() == 13.0


def test_option_snapshot_respects_replay_clock():
    spot = _frame(
        ["2026-08-11 09:15"],
        [100],
    )

    ds = PointInTimeReplayDataSource(
        spot_frames={"3m": spot},
        option_snapshots=[
            (
                datetime(2026, 8, 11, 9, 15),
                {"snapshot": "OLD"},
            ),
            (
                datetime(2026, 8, 11, 9, 30),
                {"snapshot": "FUTURE"},
            ),
        ],
        as_of=datetime(2026, 8, 11, 9, 20),
    )

    assert ds.get_option_chain()["snapshot"] == "OLD"
