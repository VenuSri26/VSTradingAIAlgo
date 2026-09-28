from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import store
from app.config import settings
from app.paper_trade_management import record_monitor_outcome
from app.routes import require_admin_token
from app.tick_bridge import get_tick_bridge

router = APIRouter()


class TickPayload(BaseModel):
    instrument_token: int | None = None
    tradingsymbol: str | None = Field(default=None, max_length=120)
    option_type: str | None = Field(default=None, pattern="^(CE|PE)$")
    strike: float | None = Field(default=None, gt=0)
    ltp: float = Field(gt=0)
    exchange_timestamp: str
    sequence: int | None = None


def _bridge():
    return get_tick_bridge(settings.tick_bridge_history_path)


@router.get("/api/tick-bridge/status")
def tick_bridge_status():
    return _bridge().status()


@router.get("/api/tick-bridge/history")
def tick_bridge_history(limit: int = 100):
    return {"history": _bridge().history(limit)}


@router.post("/api/tick-bridge/ingest", dependencies=[Depends(require_admin_token)])
def tick_bridge_ingest(body: TickPayload):
    trade = store.get_open_paper_trade()
    return _bridge().ingest(body.model_dump(), open_trade=trade, monitor=record_monitor_outcome)
