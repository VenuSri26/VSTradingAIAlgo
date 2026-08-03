"""
Core domain models for VSTradingAI decision pipeline.

Deliberately framework-agnostic (stdlib dataclasses) so the agent/pipeline
logic can be unit-tested without FastAPI/Pydantic installed. The API layer
(app/schemas.py) mirrors these 1:1 as Pydantic models for request/response
validation and OpenAPI docs.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Source(str, Enum):
    ZERODHA = "ZERODHA"
    NSE = "NSE"
    CALCULATED = "CALCULATED"
    AGENT = "AGENT"
    CACHE = "CACHE"
    MOCK = "MOCK"  # only ever present when system is explicitly in demo mode


class Availability(str, Enum):
    OK = "OK"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    STALE = "STALE"
    DATA_ERROR = "DATA_ERROR"


class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class MarketPhase(str, Enum):
    PRE_MARKET = "PRE_MARKET"
    OPENING = "OPENING"
    MORNING_TREND = "MORNING_TREND"
    MIDDAY = "MIDDAY"
    AFTERNOON = "AFTERNOON"
    POWER_HOUR = "POWER_HOUR"
    MARKET_CLOSED = "MARKET_CLOSED"


class MarketRegime(str, Enum):
    STRONG_BULLISH = "STRONG_BULLISH"
    BULLISH = "BULLISH"
    RANGE = "RANGE"
    BEARISH = "BEARISH"
    STRONG_BEARISH = "STRONG_BEARISH"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"


class TradeGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    NO_TRADE = "NO_TRADE"


class DecisionType(str, Enum):
    CE_BUY = "CE_BUY"
    PE_BUY = "PE_BUY"
    NO_TRADE = "NO_TRADE"


class HealthStatus(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


@dataclass
class DataField:
    """Wraps any live-data value with mandatory source + freshness metadata.
    Section 27 rule: nothing reaches the UI without knowing where it came from."""
    value: Optional[float]
    source: Source
    availability: Availability = Availability.OK
    timestamp: str = field(default_factory=utcnow)


@dataclass
class AgentResult:
    name: str
    score: Optional[int]  # 0-100, None if NOT_AVAILABLE
    direction: Direction
    confidence: Optional[float]  # 0-1
    reason: str
    evidence: list[str]
    weight: float
    timestamp: str = field(default_factory=utcnow)
    availability: Availability = Availability.OK


@dataclass
class AlignmentResult:
    score: Optional[int]
    bullish_contribution: float
    bearish_contribution: float
    neutral_contribution: float
    weights_used: dict[str, float]
    coverage_ratio: float = 1.0
    disagreement_score: float = 0.0
    calibrated_confidence: Optional[float] = None
    family_contributions: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=utcnow)


@dataclass
class Flag:
    category: str  # BULL | BEAR | WATCH
    text: str
    agent_source: str


@dataclass
class EntryChecklistItem:
    label: str
    passed: bool
    detail: str


@dataclass
class RiskResult:
    approved: bool
    reasons: list[str]
    trades_today: int
    max_trades: int
    daily_pnl: float
    daily_loss_limit: float
    consecutive_losses: int


@dataclass
class TradePlan:
    option_type: Optional[str]  # CE | PE | None
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
    delta: Optional[float] = None
    theta: Optional[float] = None
    iv: Optional[float] = None


@dataclass
class Decision:
    decision: DecisionType
    grade: TradeGrade
    confidence: Optional[float]
    alignment_score: Optional[int]
    plan: Optional[TradePlan]
    checklist: list[EntryChecklistItem]
    explanation: str
    timestamp: str = field(default_factory=utcnow)


@dataclass
class PositionInfo:
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


@dataclass
class SessionAnalytics:
    trades_today: int
    wins: int
    losses: int
    win_rate: Optional[float]
    gross_pnl: float
    net_pnl: float
    avg_rr: Optional[float]
    best_trade: Optional[float]
    worst_trade: Optional[float]
    a_plus_trades: int
    a_trades: int
    skipped_setups: int
    risk_blocked_setups: int


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    detail: str


@dataclass
class SystemHealth:
    components: list[ComponentHealth]
    last_tick_timestamp: Optional[str]
    data_age_sec: Optional[float]
    overall: HealthStatus


@dataclass
class LiveDecisionResponse:
    """Top-level payload for GET /api/decision/live — matches section 31/37."""
    timestamp: str
    market: dict
    regime: dict
    levels: dict
    indicators: dict
    options: dict
    gamma: dict
    liquidity: dict
    agents: list[AgentResult]
    alignment: AlignmentResult
    debate: dict
    flags: list[Flag]
    decision: Decision
    risk: RiskResult
    position: PositionInfo
    system_health: SystemHealth
    market_structure: dict
    narrative: str
