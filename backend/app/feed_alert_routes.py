from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.feed_alerts import FeedAlertHistory, evaluate_feed_alerts
from app.market_data_service import get_supervisor

router = APIRouter()


def _state():
    return get_supervisor(
        settings.market_data_state_path,
        settings.market_data_poll_interval_sec,
        settings.max_data_age_sec,
        settings.kite_websocket_requested,
    ).snapshot()


def _history():
    return FeedAlertHistory(settings.feed_alert_log_path)


@router.get("/api/feed-alerts/status")
def get_feed_alert_status():
    result = evaluate_feed_alerts(
        _state(),
        stale_after_sec=settings.max_data_age_sec,
        token_warn_age_sec=settings.token_warn_age_sec,
        token_block_age_sec=settings.token_block_age_sec,
    )
    _history().record(result)
    return result


@router.get("/api/feed-alerts/history")
def get_feed_alert_history(limit: int = 50):
    return {"history": _history().list(limit)}
