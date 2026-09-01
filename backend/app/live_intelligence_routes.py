from fastapi import APIRouter, HTTPException

from app.live_intelligence import analyse_live_market
from app.live_intelligence_history import list_history, record_snapshot, trend
from app.routes import get_data_source

router = APIRouter()


@router.get("/api/live-intelligence/status")
def live_intelligence_status(atm_range: int = 8, max_age_sec: int = 30):
    if atm_range < 2 or atm_range > 20:
        raise HTTPException(status_code=422, detail="atm_range must be between 2 and 20")
    if max_age_sec < 1 or max_age_sec > 300:
        raise HTTPException(status_code=422, detail="max_age_sec must be between 1 and 300")
    snapshot = get_data_source().get_option_chain(atm_range=atm_range)
    analysis = analyse_live_market(snapshot, max_age_sec=max_age_sec)
    persistence = record_snapshot(analysis)
    return {**analysis, "persistence": persistence}


@router.post("/api/live-intelligence/evaluate")
def evaluate_live_intelligence(payload: dict):
    snapshot = payload.get("snapshot") or payload
    max_age_sec = int(payload.get("max_age_sec", 30)) if isinstance(payload, dict) else 30
    return analyse_live_market(snapshot, max_age_sec=max_age_sec)


@router.get("/api/live-intelligence/history")
def live_intelligence_history(limit: int = 120, trading_day: str | None = None):
    return {"history": list_history(limit=limit, trading_day=trading_day)}


@router.get("/api/live-intelligence/trend")
def live_intelligence_trend(limit: int = 120, trading_day: str | None = None):
    return trend(limit=limit, trading_day=trading_day)
