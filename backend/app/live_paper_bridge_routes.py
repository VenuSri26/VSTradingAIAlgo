from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.live_intelligence_history import trend
from app.live_paper_bridge import (
    PaperSetupNotReady,
    build_paper_setup_candidate,
    prepare_paper_setup_from_preview,
    validate_confirmation_text,
)
from app.routes import get_data_source

router = APIRouter()


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN is not configured")
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")


class PrepareRequest(BaseModel):
    confirmation_text: str = Field(min_length=1, max_length=40)
    atm_range: int = Field(default=8, ge=2, le=20)
    max_age_sec: int = Field(default=30, ge=1, le=300)


def _preview(atm_range: int, max_age_sec: int):
    try:
        snapshot = get_data_source().get_option_chain(atm_range=atm_range)
        return snapshot, build_paper_setup_candidate(
            snapshot, trend(limit=60), max_age_sec=max_age_sec
        )
    except Exception as exc:
        # Broker expiry, transport failures and malformed upstream data are an
        # expected operational state. Fail closed with a useful response rather
        # than leaking a traceback as HTTP 500.
        return None, {
            "status": "BLOCKED",
            "action": "NO_TRADE",
            "execution_mode": "PAPER_PREVIEW_ONLY",
            "live_orders_enabled": False,
            "intelligence": None,
            "trend": "NO_DATA",
            "warnings": [],
            "blockers": [f"Broker data unavailable ({type(exc).__name__})"],
            "error_code": "BROKER_DATA_UNAVAILABLE",
            "candidate": None,
        }


@router.get("/api/live-paper/preview")
def preview_live_paper_setup(atm_range: int = 8, max_age_sec: int = 30):
    if atm_range < 2 or atm_range > 20:
        raise HTTPException(status_code=422, detail="atm_range must be between 2 and 20")
    if max_age_sec < 1 or max_age_sec > 300:
        raise HTTPException(status_code=422, detail="max_age_sec must be between 1 and 300")
    _, result = _preview(atm_range, max_age_sec)
    return result


@router.post("/api/live-paper/prepare", dependencies=[Depends(require_admin_token)])
def prepare_live_paper_setup(body: PrepareRequest):
    try:
        validate_confirmation_text(body.confirmation_text)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _, result = _preview(body.atm_range, body.max_age_sec)
    try:
        return prepare_paper_setup_from_preview(result)
    except PaperSetupNotReady as e:
        raise HTTPException(status_code=409, detail=e.result)


@router.get("/api/paper/automation/status")
def paper_automation_status():
    from app.paper_auto_trader import status_snapshot
    return status_snapshot()


@router.get("/api/paper/readiness")
def paper_readiness():
    from app.paper_loop_readiness import paper_loop_readiness
    return paper_loop_readiness()


@router.post("/api/paper/automation/run-once", dependencies=[Depends(require_admin_token)])
def paper_automation_run_once():
    from app.paper_auto_trader import run_once
    return run_once(get_data_source())
