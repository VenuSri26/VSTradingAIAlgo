from datetime import date

import pandas as pd

from app.futures_volume import (
    build_futures_volume_snapshot,
    select_nearest_nifty_future,
)


def test_select_nearest_nifty_future():
    instruments = [
        {
            "name": "NIFTY",
            "tradingsymbol": "NIFTY26SEPFUT",
            "instrument_type": "FUT",
            "segment": "NFO-FUT",
            "expiry": date(2026, 9, 29),
            "instrument_token": 2,
        },
        {
            "name": "NIFTY",
            "tradingsymbol": "NIFTY26AUGFUT",
            "instrument_type": "FUT",
            "segment": "NFO-FUT",
            "expiry": date(2026, 8, 25),
            "instrument_token": 1,
        },
    ]

    result = select_nearest_nifty_future(
        instruments,
        today=date(2026, 8, 12),
    )

    assert result["tradingsymbol"] == "NIFTY26AUGFUT"
    assert result["instrument_token"] == 1


def test_volume_snapshot():
    idx = pd.date_range(
        "2026-08-12 09:15",
        periods=25,
        freq="3min",
        tz="Asia/Kolkata",
    )

    df = pd.DataFrame(
        {
            "open": [24500 + i for i in range(25)],
            "high": [24505 + i for i in range(25)],
            "low": [24495 + i for i in range(25)],
            "close": [24502 + i for i in range(25)],
            "volume": [1000] * 24 + [1500],
        },
        index=idx,
    )

    result = build_futures_volume_snapshot(
        df,
        spot_close=24520.0,
    )

    assert result["status"] == "READY"
    assert result["session_volume"] == 25500.0
    assert result["relative_volume"] == 1.5
    assert result["volume_confirmed"] is True
    assert result["futures_vwap"] is not None
    assert result["spot_equivalent_vwap"] is not None


def test_zero_volume_is_safe():
    idx = pd.date_range(
        "2026-08-12 09:15",
        periods=5,
        freq="3min",
        tz="Asia/Kolkata",
    )

    df = pd.DataFrame(
        {
            "open": [100] * 5,
            "high": [101] * 5,
            "low": [99] * 5,
            "close": [100] * 5,
            "volume": [0] * 5,
        },
        index=idx,
    )

    result = build_futures_volume_snapshot(df)

    assert result["status"] == "READY"
    assert result["futures_vwap"] is None
    assert result["relative_volume"] == 0.0
    assert result["volume_confirmed"] is False


def test_merge_futures_volume_into_indicators():
    from app.futures_volume import merge_futures_volume_into_indicators

    indicators = {
        "close": 24471.7,
        "vwap": None,
        "volume": 0.0,
        "avg_volume": 0.0,
        "relative_volume": 0.0,
        "rsi14": 63.9,
    }

    snapshot = {
        "status": "READY",
        "futures_close": 24525.1,
        "futures_vwap": 24535.635,
        "spot_equivalent_vwap": 24482.235,
        "basis": 53.4,
        "last_volume": 10075.0,
        "avg_volume": 15203.5,
        "relative_volume": 0.6627,
        "session_volume": 1244165.0,
        "volume_confirmed": False,
        "source": "ZERODHA_NIFTY_FUTURES",
    }

    meta = {
        "tradingsymbol": "NIFTY26AUGFUT",
        "expiry": "2026-08-25",
    }

    result = merge_futures_volume_into_indicators(
        indicators,
        snapshot,
        meta,
    )

    assert result["close"] == 24471.7
    assert result["rsi14"] == 63.9
    assert result["vwap"] == 24482.235
    assert result["volume"] == 10075.0
    assert result["relative_volume"] == 0.6627
    assert result["futures_vwap"] == 24535.635
    assert result["futures_basis"] == 53.4
    assert result["futures_symbol"] == "NIFTY26AUGFUT"
    assert result["volume_confirmed"] is False
    assert result["volume_source"] == "ZERODHA_NIFTY_FUTURES"


def test_merge_not_ready_preserves_existing_indicators():
    from app.futures_volume import merge_futures_volume_into_indicators

    original = {
        "close": 24471.7,
        "vwap": None,
        "volume": 0.0,
    }

    result = merge_futures_volume_into_indicators(
        original,
        {"status": "NOT_AVAILABLE"},
        {},
    )

    assert result == original


def test_merge_futures_volume_into_features():
    from dataclasses import dataclass
    from app.futures_volume import merge_futures_volume_into_features

    @dataclass
    class DummyFeatures:
        close: float
        vwap: float
        volume: float
        avg_volume: float
        relative_volume: float
        rsi14: float

    original = DummyFeatures(
        close=24471.7,
        vwap=0.0,
        volume=0.0,
        avg_volume=0.0,
        relative_volume=0.0,
        rsi14=63.97,
    )

    snapshot = {
        "status": "READY",
        "spot_equivalent_vwap": 24482.235,
        "last_volume": 10075.0,
        "avg_volume": 15203.5,
        "relative_volume": 0.6627,
    }

    result = merge_futures_volume_into_features(
        original,
        snapshot,
    )

    assert result.close == 24471.7
    assert result.rsi14 == 63.97
    assert result.vwap == 24482.235
    assert result.volume == 10075.0
    assert result.avg_volume == 15203.5
    assert result.relative_volume == 0.6627


def test_merge_futures_features_fail_open():
    from dataclasses import dataclass
    from app.futures_volume import merge_futures_volume_into_features

    @dataclass
    class DummyFeatures:
        vwap: float
        volume: float
        avg_volume: float
        relative_volume: float

    original = DummyFeatures(
        vwap=11.0,
        volume=22.0,
        avg_volume=33.0,
        relative_volume=0.8,
    )

    result = merge_futures_volume_into_features(
        original,
        {"status": "NOT_AVAILABLE"},
    )

    assert result == original
