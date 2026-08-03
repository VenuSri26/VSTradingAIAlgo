"""
Pydantic response models — the API-layer mirror of app/models.py dataclasses.
Kept separate so the pipeline/agents have zero FastAPI/Pydantic dependency
and can be unit tested with plain Python (see tests/test_pipeline.py).

`from_dataclass` converts a models.py dataclass tree into these schemas at
the route boundary.
"""
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, Any


class AgentResultSchema(BaseModel):
    name: str
    score: Optional[int]
    direction: str
    confidence: Optional[float]
    reason: str
    evidence: list[str]
    weight: float
    timestamp: str
    availability: str


class AlignmentSchema(BaseModel):
    score: Optional[int]
    bullish_contribution: float
    bearish_contribution: float
    neutral_contribution: float
    weights_used: dict[str, float]
    coverage_ratio: float = 1.0
    disagreement_score: float = 0.0
    calibrated_confidence: Optional[float] = None
    family_contributions: dict[str, float] = {}
    timestamp: str


class FlagSchema(BaseModel):
    category: str
    text: str
    agent_source: str


class EntryChecklistItemSchema(BaseModel):
    label: str
    passed: bool
    detail: str


class TradePlanSchema(BaseModel):
    option_type: Optional[str]
    strike: Optional[int]
    ltp: Optional[float]
    entry_low: Optional[float]
    entry_high: Optional[float]
    trigger: Optional[str]
    confirmation: Optional[str]
    stop_loss: Optional[float]
    target_1: Optional[float]
    target_2: Optional[float]
    risk_reward: Optional[float]
    max_risk_rupees: Optional[float]
    invalidation: Optional[str]


class DecisionSchema(BaseModel):
    decision: str
    grade: str
    confidence: Optional[float]
    alignment_score: Optional[int]
    plan: Optional[TradePlanSchema]
    checklist: list[EntryChecklistItemSchema]
    explanation: str
    timestamp: str


class RiskResultSchema(BaseModel):
    approved: bool
    reasons: list[str]
    trades_today: int
    max_trades: int
    daily_pnl: float
    daily_loss_limit: float
    consecutive_losses: int


class PositionInfoSchema(BaseModel):
    has_position: bool
    option_type: Optional[str] = None
    strike: Optional[int] = None
    quantity: Optional[int] = None
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    stop_loss: Optional[float] = None
    target_1: Optional[float] = None
    target_2: Optional[float] = None
    status: Optional[str] = None
    time_in_trade_sec: Optional[int] = None


class ComponentHealthSchema(BaseModel):
    name: str
    status: str
    detail: str


class SystemHealthSchema(BaseModel):
    components: list[ComponentHealthSchema]
    last_tick_timestamp: Optional[str]
    data_age_sec: Optional[float]
    overall: str


class LiveDecisionResponseSchema(BaseModel):
    timestamp: str
    market: dict[str, Any]
    regime: dict[str, Any]
    levels: dict[str, Any]
    indicators: dict[str, Any]
    options: dict[str, Any]
    gamma: dict[str, Any]
    liquidity: dict[str, Any]
    agents: list[AgentResultSchema]
    alignment: AlignmentSchema
    debate: dict[str, Any] = {}
    flags: list[FlagSchema]
    decision: DecisionSchema
    risk: RiskResultSchema
    position: PositionInfoSchema
    system_health: SystemHealthSchema
    market_structure: dict[str, Any]
    narrative: str


def from_dataclass(resp) -> LiveDecisionResponseSchema:
    from dataclasses import asdict
    d = asdict(resp)
    # asdict() turns Enums into their .value automatically only for plain
    # fields; nested enums inside dataclasses are preserved as Enum objects
    # by asdict in some versions, so normalise explicitly:
    def enum_to_val(x):
        if isinstance(x, dict):
            return {k: enum_to_val(v) for k, v in x.items()}
        if isinstance(x, list):
            return [enum_to_val(v) for v in x]
        if hasattr(x, "value") and not isinstance(x, (int, float, str, bool)):
            return x.value
        return x
    d = enum_to_val(d)
    return LiveDecisionResponseSchema(**d)
