from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import store
from app.config import settings
from app.paper_trade_management import evaluate
from app.routes import require_admin_token
from app.tick_bridge import get_tick_bridge
from app.kite_stream_manager import get_stream_manager

router = APIRouter()


def _manager():
    return get_stream_manager(settings.kite_websocket_requested, settings.websocket_batch_size, settings.websocket_queue_size)


def _monitor(trade: dict, price: float):
    result = evaluate(trade, price)
    detail = ",".join(result.get("actions") or []) or result.get("reason")
    store.record_paper_monitor_event(trade["id"], price, result["action"], detail)
    if result["action"] == "CLOSED" and result.get("net_pnl") is not None:
        store.record_trade_result(result["net_pnl"], "B")
    return result


def _ingest(tick: dict):
    bridge = get_tick_bridge(settings.tick_bridge_history_path)
    trade = store.get_open_paper_trade()
    return bridge.ingest(tick, open_trade=trade, monitor=_monitor)


class SubscriptionPayload(BaseModel):
    instrument_tokens: list[int] = Field(default_factory=list, max_length=500)


class BatchPayload(BaseModel):
    ticks: list[dict] = Field(default_factory=list, max_length=5000)


class DisconnectPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.get("/api/kite-stream/status")
def kite_stream_status():
    return _manager().status()


@router.get("/api/kite-stream/history")
def kite_stream_history(limit: int = 20):
    return {"history": _manager().history(limit)}


@router.post("/api/kite-stream/subscriptions", dependencies=[Depends(require_admin_token)])
def kite_stream_subscribe(body: SubscriptionPayload):
    return _manager().subscribe(body.instrument_tokens)


@router.post("/api/kite-stream/connect", dependencies=[Depends(require_admin_token)])
def kite_stream_connect():
    return _manager().mark_connected()


@router.post("/api/kite-stream/disconnect", dependencies=[Depends(require_admin_token)])
def kite_stream_disconnect(body: DisconnectPayload):
    return _manager().mark_disconnected(body.reason)


@router.post("/api/kite-stream/ticks", dependencies=[Depends(require_admin_token)])
def kite_stream_ticks(body: BatchPayload):
    return _manager().ingest_batch(body.ticks, _ingest)
