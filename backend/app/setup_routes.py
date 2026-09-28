from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.live_paper_bridge_routes import require_admin_token
from app.routes import get_data_source
from app.setup_service import kite_login_url, refresh_kite_token, save_preferences, status

router = APIRouter()


class Preferences(BaseModel):
    minimum_confidence: int = Field(ge=70, le=90)
    capital: float = Field(ge=10000, le=200000)
    profit_withdrawal_threshold: float = Field(ge=0, le=10_000_000)
    default_stop_loss_pct: float = Field(ge=1, le=50)


class RedirectPayload(BaseModel):
    redirect_url: str = Field(min_length=10, max_length=2048)


def _health() -> dict:
    try:
        source = get_data_source()
        if not hasattr(source, "token_health"):
            return {"connected": False, "source": "NOT_CONFIGURED"}
        return source.token_health()
    except Exception as exc:
        return {"connected": False, "error": f"{type(exc).__name__}: {exc}"}


@router.get("/api/setup/status")
def setup_status():
    return status(_health())


@router.put("/api/setup/preferences", dependencies=[Depends(require_admin_token)])
def update_preferences(body: Preferences):
    try:
        return save_preferences(**body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/api/setup/zerodha/login-url", dependencies=[Depends(require_admin_token)])
def zerodha_login_url():
    try:
        return {"login_url": kite_login_url(), "expires": "single-use daily request token",
                "live_orders_enabled": False}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/setup/zerodha/refresh", dependencies=[Depends(require_admin_token)])
def zerodha_refresh(body: RedirectPayload, request: Request):
    forwarded = request.headers.get("x-forwarded-proto", request.url.scheme).lower()
    if forwarded != "https":
        raise HTTPException(status_code=426, detail="HTTPS is required before entering a Zerodha redirect URL in the UI")
    try:
        return refresh_kite_token(body.redirect_url)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Zerodha token exchange failed; no credential was saved") from exc
