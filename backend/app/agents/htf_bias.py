from __future__ import annotations
import pandas as pd
from app.models import AgentResult, Direction, utcnow
from app.features import ema
from .base import clamp, direction_from_score, to_public_score

TIMEFRAMES = ["monthly", "weekly", "daily", "15m", "5m", "3m"]


def _tf_bias(df: pd.DataFrame) -> tuple[Direction, float]:
    """Simple, honest bias per timeframe: last close vs EMA20 of that
    timeframe's closes, scaled by distance."""
    if len(df) < 5:
        return Direction.NEUTRAL, 0.0
    closes = df["close"]
    e20 = ema(closes, min(20, len(closes)))
    last, e = float(closes.iloc[-1]), float(e20.iloc[-1])
    pct = (last - e) / e * 100
    signed = clamp(pct * 50, -100, 100)
    return direction_from_score(signed), signed


def htf_bias_agent(candles_by_tf: dict[str, pd.DataFrame], weight: float) -> AgentResult:
    """candles_by_tf: dict mapping each of TIMEFRAMES -> OHLC DataFrame.
    Missing timeframes are skipped (not fabricated) and noted in evidence."""
    per_tf_scores = []
    evidence = []
    missing = []

    for tf in TIMEFRAMES:
        df = candles_by_tf.get(tf)
        if df is None or df.empty:
            missing.append(tf)
            continue
        direction, signed = _tf_bias(df)
        per_tf_scores.append(signed)
        evidence.append(f"{tf}: {direction.value} ({signed:+.0f})")

    if missing:
        evidence.append(f"Missing data for: {', '.join(missing)} (excluded from alignment)")

    if not per_tf_scores:
        return AgentResult(
            name="Higher Timeframe Bias Agent", score=None, direction=Direction.NOT_AVAILABLE,
            confidence=None, reason="No timeframe data available.", evidence=evidence,
            weight=weight, timestamp=utcnow(),
        )

    avg_signed = sum(per_tf_scores) / len(per_tf_scores)
    agreement = sum(1 for s in per_tf_scores if (s > 0) == (avg_signed > 0)) / len(per_tf_scores)
    # alignment score rewards both direction strength AND cross-timeframe agreement
    alignment_signed = avg_signed * agreement
    direction = direction_from_score(alignment_signed)

    return AgentResult(
        name="Higher Timeframe Bias Agent",
        score=to_public_score(alignment_signed),
        direction=direction,
        confidence=round(agreement, 2),
        reason=f"{len(per_tf_scores)}/{len(TIMEFRAMES)} timeframes analysed, {agreement*100:.0f}% agree on {direction.value.lower()} bias.",
        evidence=evidence, weight=weight, timestamp=utcnow(),
    )
