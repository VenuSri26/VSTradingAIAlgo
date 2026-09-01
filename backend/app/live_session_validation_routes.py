from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.config import settings
from app.routes import require_admin_token
from app.live_session_recorder import get_live_session_recorder, get_live_session_service

router = APIRouter()
_service = get_live_session_service()

class SessionSample(BaseModel):
    trading_day: str | None = None
    feed_age_sec: float = Field(ge=0)
    websocket_connected: bool = False
    authenticated: bool = True
    market_open: bool = True
    option_chain_ready: bool = False
    tick_bridge_ready: bool = False
    errors: list[str] = []

@router.get("/api/live-session-validation/status")
def status(limit: int = 500, trading_day: str | None = None):
    return _service.summary(limit, trading_day)

@router.get("/api/live-session-validation/history")
def history(limit: int = 200, trading_day: str | None = None):
    return {"items": _service.history(limit, trading_day), "summary": _service.summary(limit, trading_day)}

@router.get("/api/live-session-validation/sessions")
def sessions(limit_days: int = 10):
    return _service.multi_session_report(limit_days)

@router.get("/api/live-session-validation/recorder")
def recorder_status():
    return get_live_session_recorder().status()

@router.post("/api/live-session-validation/record", dependencies=[Depends(require_admin_token)])
def record(body: SessionSample):
    return _service.record(body.model_dump())

@router.post("/api/live-session-validation/record-now", dependencies=[Depends(require_admin_token)])
def record_now():
    from app.kite_ticker_runtime import get_kite_ticker_runtime
    from app.market_safety_routes import get_market_safety_status
    from app.tick_bridge_routes import tick_bridge_status
    return get_live_session_recorder().record_once(
        get_kite_ticker_runtime().status(),
        get_market_safety_status(),
        tick_bridge_status(),
    )
