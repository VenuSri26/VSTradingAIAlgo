from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.kite_ticker_runtime import get_kite_ticker_runtime
from app.market_data_service import get_supervisor
from app.routes import get_data_source
from app.live_market_engine import LiveMarketEngine
from app.live_market_realtime import LiveMarketRealtime

router = APIRouter()


def _engine() -> LiveMarketEngine:
    return LiveMarketEngine(
        get_data_source(),
        get_kite_ticker_runtime(),
        get_supervisor(
            settings.market_data_state_path,
            settings.market_data_poll_interval_sec,
            settings.max_data_age_sec,
            settings.kite_websocket_requested,
        ),
    )


@router.get("/api/live-market/status")
def live_market_status():
    return _engine().status()


@router.get("/api/live-market/sources")
def live_market_sources():
    return _engine().sources()


@router.get("/api/live-market/snapshot")
def live_market_snapshot(atm_range: int = 8, candle_lookback: int = 120):
    if atm_range < 2 or atm_range > 20:
        raise HTTPException(status_code=422, detail="atm_range must be between 2 and 20")
    if candle_lookback < 20 or candle_lookback > 500:
        raise HTTPException(status_code=422, detail="candle_lookback must be between 20 and 500")
    return _engine().snapshot(atm_range=atm_range, candle_lookback=candle_lookback)


def _realtime() -> LiveMarketRealtime:
    return LiveMarketRealtime(get_data_source(), get_kite_ticker_runtime())


@router.get("/api/live-market/feed")
def live_market_feed():
    return _realtime().feed()


@router.get("/api/live-market/ticks")
def live_market_ticks(limit: int = 100, instrument_token: int | None = None):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    return _realtime().ticks(limit=limit, instrument_token=instrument_token)


@router.get("/api/live-market/candles")
def live_market_candles(timeframe: str = "3m", limit: int = 120, include_current: bool = True):
    if timeframe not in {"1m", "3m", "5m"}:
        raise HTTPException(status_code=422, detail="timeframe must be one of 1m, 3m, 5m")
    if limit < 1 or limit > 600:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 600")
    return _realtime().candles(timeframe=timeframe, limit=limit, include_current=include_current)


@router.get("/api/live-market/indicators")
def live_market_indicators(lookback: int = 120):
    if lookback < 60 or lookback > 500:
        raise HTTPException(status_code=422, detail="lookback must be between 60 and 500")
    return _realtime().indicators(lookback=lookback)
