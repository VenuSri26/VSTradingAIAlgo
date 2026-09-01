from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.feed_watchdog import evaluate_feed_safety
from app.market_data_service import get_supervisor
from app.market_clock import market_clock, normalize_exchange_timestamp

router = APIRouter()


def _supervisor():
    return get_supervisor(
        settings.market_data_state_path,
        settings.market_data_poll_interval_sec,
        settings.max_data_age_sec,
        settings.kite_websocket_requested,
    )


@router.get("/api/market-safety/status")
def get_market_safety_status():
    state = _supervisor().snapshot()
    return evaluate_feed_safety(
        state,
        stale_after_sec=settings.max_data_age_sec,
        holidays=settings.market_holidays,
        open_time=settings.market_open_time,
        close_time=settings.market_close_time,
    )


@router.get("/api/market-safety/clock")
def get_market_clock():
    return market_clock(
        holidays=settings.market_holidays,
        open_time=settings.market_open_time,
        close_time=settings.market_close_time,
    ).to_dict()


@router.post("/api/market-safety/normalize-timestamp")
def post_normalize_timestamp(payload: dict):
    return {"input": payload.get("timestamp"), "normalized_utc": normalize_exchange_timestamp(payload.get("timestamp"))}
