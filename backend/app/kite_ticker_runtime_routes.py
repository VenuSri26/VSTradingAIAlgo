from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.routes import get_data_source, require_admin_token
from app.kite_ticker_runtime import get_kite_ticker_runtime
from app.data_sources.zerodha_client import INDIA_VIX_TOKEN, NIFTY_INSTRUMENT_TOKEN

router = APIRouter()


class StopPayload(BaseModel):
    reason: str = Field(default="manual stop", max_length=300)


@router.get("/api/kite-runtime/status")
def runtime_status():
    return get_kite_ticker_runtime().status()


@router.post("/api/kite-runtime/start", dependencies=[Depends(require_admin_token)])
def runtime_start():
    return get_kite_ticker_runtime().start()


@router.post("/api/kite-runtime/stop", dependencies=[Depends(require_admin_token)])
def runtime_stop(body: StopPayload):
    return get_kite_ticker_runtime().stop(body.reason)


@router.post("/api/kite-runtime/sync-subscriptions", dependencies=[Depends(require_admin_token)])
def runtime_sync_subscriptions(atm_range: int = 8):
    if atm_range < 2 or atm_range > 20:
        raise HTTPException(status_code=422, detail="atm_range must be between 2 and 20")
    snapshot = get_data_source().get_option_chain(atm_range=atm_range)
    contracts = [
        {"instrument_token": NIFTY_INSTRUMENT_TOKEN, "tradingsymbol": "NIFTY 50", "asset_type": "NIFTY_INDEX"},
        {"instrument_token": INDIA_VIX_TOKEN, "tradingsymbol": "INDIA VIX", "asset_type": "INDIA_VIX"},
    ]
    for option_type in ("CE", "PE"):
        for item in snapshot.get("chain", {}).get(option_type, []):
            if item.get("instrument_token"):
                contracts.append({
                    "instrument_token": item.get("instrument_token"),
                    "tradingsymbol": item.get("tradingsymbol"),
                    "option_type": option_type,
                    "strike": item.get("strike"),
                    "expiry": snapshot.get("expiry"),
                })
    result = get_kite_ticker_runtime().configure_contracts(contracts)
    return {**result, "expiry": snapshot.get("expiry"), "atm": snapshot.get("atm")}
