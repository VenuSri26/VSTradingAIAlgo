from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.learning_engine import TradeObservation, performance_metrics, confidence_calibration, agent_performance, grouped_performance, walk_forward_splits

router = APIRouter(prefix="/api", tags=["learning"])

class TradeInput(BaseModel):
    pnl: float
    confidence: float = Field(ge=0, le=100)
    regime: str = "UNKNOWN"
    strategy: str = "AI_COMPOSITE"
    agent_votes: dict[str, float] = Field(default_factory=dict)

class LearningRequest(BaseModel):
    trades: list[TradeInput]
    initial_capital: float = Field(default=100000, gt=0)

class WalkForwardRequest(BaseModel):
    observations: list[dict[str, Any]]
    train_size: int = Field(gt=0)
    test_size: int = Field(gt=0)
    step_size: int | None = Field(default=None, gt=0)

def _rows(payload: LearningRequest) -> list[TradeObservation]:
    return [TradeObservation(**item.model_dump()) for item in payload.trades]

@router.get("/learning/capabilities")
def capabilities():
    return {"version":"2.9.0-rc.1","mode":"PAPER_LEARNING_ONLY","features":[
        "performance_metrics","confidence_calibration","agent_reliability","regime_analysis","strategy_ranking","walk_forward_splits"],
        "minimum_recommended_samples":30,"automatic_weight_updates":False,"live_orders_enabled":False}

@router.post("/learning/evaluate")
def evaluate(payload: LearningRequest):
    rows=_rows(payload)
    return {"performance":performance_metrics(rows,payload.initial_capital),
            "calibration":confidence_calibration(rows),"agents":agent_performance(rows),
            "regimes":grouped_performance(rows,"regime"),"strategies":grouped_performance(rows,"strategy"),
            "safety":{"automatic_weight_updates":False,"live_orders_enabled":False}}

@router.post("/optimization/walk-forward")
def walk_forward(payload: WalkForwardRequest):
    try: windows=walk_forward_splits(payload.observations,payload.train_size,payload.test_size,payload.step_size)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {"window_count":len(windows),"windows":windows,"mode":"RESEARCH_ONLY"}
