from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.consensus_shadow import get_consensus_shadow_recorder
from app.market_data_service import get_supervisor
from app.routes import require_admin_token
from app.secondary_market_data import get_secondary_quote_adapter
from app.consensus_certification import certify_consensus_shadow
from app.upstox_market_data import get_upstox_quote_adapter

router = APIRouter()


class SecondaryQuotePayload(BaseModel):
    source: str = Field(min_length=1, max_length=60)
    instrument: str = Field(min_length=1, max_length=120)
    last_price: float = Field(gt=0)
    exchange_timestamp: str
    received_at: str | None = None
    instrument_token: int | None = None
    provider_instrument_id: str | None = Field(default=None, max_length=160)
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    sequence: int | None = None


def _adapter():
    return get_secondary_quote_adapter(settings.secondary_quote_replay_path)


def _recorder():
    return get_consensus_shadow_recorder(settings.consensus_shadow_history_path)


def _certification():
    return certify_consensus_shadow(
        _recorder().history(_recorder().max_history),
        min_samples=settings.consensus_cert_min_samples,
        min_sessions=settings.consensus_cert_min_sessions,
        min_verified_ratio=settings.consensus_cert_min_verified_ratio,
        max_conflict_ratio=settings.consensus_cert_max_conflict_ratio,
        max_stale_ratio=settings.consensus_cert_max_stale_ratio,
        max_p95_deviation_pct=settings.consensus_cert_max_p95_deviation_pct,
    )


@router.get("/api/market-data-consensus/status")
def consensus_status():
    supervisor = get_supervisor(
        settings.market_data_state_path,
        settings.market_data_poll_interval_sec,
        settings.max_data_age_sec,
        settings.kite_websocket_requested,
    )
    return {
        "enforcement_required": settings.market_data_consensus_required,
        "current_consensus": supervisor.snapshot().get("source_consensus"),
        "secondary_adapter": (
            get_upstox_quote_adapter(
                settings.upstox_access_token,
                settings.upstox_nifty_instrument_key,
                settings.upstox_quote_timeout_sec,
                settings.upstox_quote_poll_interval_sec,
            ).status()
            if settings.upstox_market_data_enabled else _adapter().status()
        ),
        "shadow": _recorder().summary(),
        "certification": _certification(),
        "live_orders_enabled": False,
    }


@router.get("/api/market-data-consensus/history")
def consensus_history(limit: int = 100):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    return {"history": _recorder().history(limit)}


@router.get("/api/market-data-consensus/certification")
def consensus_certification():
    return _certification()


@router.post("/api/market-data-consensus/secondary/ingest", dependencies=[Depends(require_admin_token)])
def ingest_secondary_quote(body: SecondaryQuotePayload):
    envelope = _adapter().ingest(body.model_dump(exclude_none=True))
    return {
        "status": "ACCEPTED",
        "envelope": envelope.to_dict(),
        "execution_capability": False,
        "note": "Quote stored for shadow consensus; it cannot place orders.",
    }
