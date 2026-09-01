from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from app.test_scenarios import ScenarioInput, evaluate_scenario, run_release_scenarios

router = APIRouter(prefix="/api/test-scenarios", tags=["test-scenarios"])


class ScenarioRequest(BaseModel):
    dominant_direction: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    alignment_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    risk_approved: bool = True
    data_fresh: bool = True
    htf_aligned: bool = True
    vwap_aligned: bool = True
    ema_aligned: bool = True
    momentum_confirmed: bool = True
    options_supportive: bool = True
    no_trap: bool = True
    risk_reward: float | None = Field(default=1.5, ge=0)
    market_open: bool = True


@router.get("")
def get_release_test_scenarios():
    return run_release_scenarios()


@router.post("/evaluate")
def evaluate_custom_scenario(body: ScenarioRequest):
    scenario = ScenarioInput(name="custom", description="User supplied deterministic scenario", **body.model_dump())
    actual, grade, blockers = evaluate_scenario(scenario)
    if actual not in {"CE_BUY", "PE_BUY", "NO_TRADE"}:
        raise HTTPException(status_code=500, detail="Unexpected decision")
    return {"decision": actual, "grade": grade, "blockers": blockers, "input": body.model_dump(), "live_orders_enabled": False}
