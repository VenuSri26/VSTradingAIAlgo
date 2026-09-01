from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.live_intelligence_history import trend
from app.live_paper_bridge import build_paper_setup_candidate
from app.routes import get_data_source
from app import store

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
    snapshot = get_data_source().get_option_chain(atm_range=atm_range)
    return snapshot, build_paper_setup_candidate(
        snapshot, trend(limit=60), max_age_sec=max_age_sec
    )


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
    if body.confirmation_text != "PREPARE_PAPER_SETUP":
        raise HTTPException(status_code=409, detail="Type PREPARE_PAPER_SETUP to create a draft")
    snapshot, result = _preview(body.atm_range, body.max_age_sec)
    if result["status"] != "READY_FOR_HUMAN_REVIEW":
        raise HTTPException(status_code=409, detail=result)
    c = result["candidate"]
    payload = {
        "timestamp": c["captured_at"],
        "decision": {
            "decision": c["decision"],
            "grade": c["grade"],
            "alignment_score": c["alignment_score"],
            "explanation": "; ".join(c["rationale"]),
            "plan": {
                "option_type": c["option_type"], "strike": c["strike"],
                "entry_low": c["entry_low"], "entry_high": c["entry_high"],
                "stop_loss": c["stop_loss"], "target_1": c["target_1"],
                "target_2": c["target_2"], "risk_reward": c["risk_reward"],
            },
        },
        "live_intelligence": result["intelligence"],
        "live_trend": result["trend"],
        "source": "LIVE_PAPER_BRIDGE",
        "execution_mode": "PAPER_ONLY",
    }
    setup_id = store.create_trade_setup(result["signature"], payload)
    if setup_id is None:
        matches = store.list_trade_setups(limit=20)
        existing = next((x for x in matches if x.get("signature") == result["signature"]), None)
        return {"created": False, "reason": "DUPLICATE", "setup": existing, **result}
    setup = store.get_trade_setup(setup_id)
    return {"created": True, "setup": setup, **result}
