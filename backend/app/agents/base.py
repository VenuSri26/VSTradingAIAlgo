from __future__ import annotations
from app.models import AgentResult, Direction, Availability, utcnow


def clamp(v: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, v))


def direction_from_score(score: float, neutral_band: float = 8.0) -> Direction:
    """Score is on a -100..+100 signed scale internally before we clamp/shift
    to the public 0-100 scale. Callers pass the signed value here."""
    if score > neutral_band:
        return Direction.BULLISH
    if score < -neutral_band:
        return Direction.BEARISH
    return Direction.NEUTRAL


def to_public_score(signed_score: float) -> int:
    """Map a -100..+100 signed conviction score to the 0-100 magnitude score
    shown on the dashboard (spec wants 0-100 bars, direction shown separately)."""
    return int(round(clamp(abs(signed_score))))


def not_available(name: str, weight: float, reason: str) -> AgentResult:
    return AgentResult(
        name=name, score=None, direction=Direction.NOT_AVAILABLE, confidence=None,
        reason=reason, evidence=[], weight=weight, timestamp=utcnow(),
        availability=Availability.NOT_AVAILABLE,
    )
