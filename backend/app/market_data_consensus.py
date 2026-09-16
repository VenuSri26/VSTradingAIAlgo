"""Typed market-data evidence and deterministic multi-source consensus.

This module never authorizes a trade.  It converts provider-specific quotes
into a canonical envelope and produces auditable evidence for the existing
execution DataQualityGate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any, Iterable


class ConsensusStatus(str, Enum):
    VERIFIED = "VERIFIED"
    DEGRADED = "DEGRADED"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"


def _utc(value: datetime | str) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("market timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class MarketDataEnvelopeV2:
    source: str
    instrument: str
    instrument_token: int | None
    provider_instrument_id: str | None
    exchange_timestamp: str
    received_at: str
    last_price: float
    bid: float | None = None
    ask: float | None = None
    sequence: int | None = None
    schema_version: str = "2.0"

    @classmethod
    def create(
        cls,
        *,
        source: str,
        instrument: str,
        last_price: float,
        exchange_timestamp: datetime | str,
        received_at: datetime | str | None = None,
        instrument_token: int | None = None,
        provider_instrument_id: str | None = None,
        bid: float | None = None,
        ask: float | None = None,
        sequence: int | None = None,
    ) -> "MarketDataEnvelopeV2":
        source = str(source or "").strip().upper()
        instrument = str(instrument or "").strip().upper()
        if not source or not instrument:
            raise ValueError("source and instrument are required")
        price = float(last_price)
        if not isfinite(price) or price <= 0:
            raise ValueError("last_price must be finite and positive")
        exchange_dt = _utc(exchange_timestamp)
        received_dt = _utc(received_at or datetime.now(timezone.utc))
        if exchange_dt > received_dt:
            raise ValueError("exchange timestamp cannot be after received timestamp")
        normalized_bid = float(bid) if bid is not None else None
        normalized_ask = float(ask) if ask is not None else None
        if normalized_bid is not None and (not isfinite(normalized_bid) or normalized_bid <= 0):
            raise ValueError("bid must be finite and positive")
        if normalized_ask is not None and (not isfinite(normalized_ask) or normalized_ask <= 0):
            raise ValueError("ask must be finite and positive")
        if normalized_bid is not None and normalized_ask is not None and normalized_ask < normalized_bid:
            raise ValueError("crossed quote is not valid")
        return cls(
            source=source,
            instrument=instrument,
            instrument_token=int(instrument_token) if instrument_token is not None else None,
            provider_instrument_id=str(provider_instrument_id).strip() if provider_instrument_id else None,
            exchange_timestamp=exchange_dt.isoformat(),
            received_at=received_dt.isoformat(),
            last_price=price,
            bid=normalized_bid,
            ask=normalized_ask,
            sequence=int(sequence) if sequence is not None else None,
        )

    def age_sec(self, now: datetime | None = None) -> float:
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        return max(0.0, (reference - _utc(self.exchange_timestamp)).total_seconds())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceConsensusDecision:
    status: ConsensusStatus
    approved: bool
    blockers: list[str]
    warnings: list[str]
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


def evaluate_source_consensus(
    envelopes: Iterable[MarketDataEnvelopeV2],
    *,
    now: datetime | None = None,
    max_age_sec: float = 10.0,
    max_price_deviation_pct: float = 0.15,
    min_sources: int = 2,
) -> SourceConsensusDecision:
    items = list(envelopes)
    blockers: list[str] = []
    warnings: list[str] = []
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    unique_sources = {item.source for item in items}
    instruments = {item.instrument for item in items}
    fresh = [item for item in items if item.age_sec(current) <= max_age_sec]

    evidence: dict[str, Any] = {
        "schema_version": "2.0",
        "required_sources": int(min_sources),
        "observed_sources": sorted(unique_sources),
        "fresh_sources": sorted({item.source for item in fresh}),
        "max_age_sec": float(max_age_sec),
        "max_price_deviation_pct": float(max_price_deviation_pct),
        "quotes": [item.to_dict() for item in items],
    }
    if not items or not fresh:
        blockers.append("CONSENSUS_ALL_SOURCES_STALE")
        return SourceConsensusDecision(ConsensusStatus.STALE, False, blockers, warnings, evidence)
    if len(instruments) != 1:
        blockers.append("CONSENSUS_INSTRUMENT_MISMATCH")
        return SourceConsensusDecision(ConsensusStatus.CONFLICTED, False, blockers, warnings, evidence)
    if len(unique_sources) != len(items):
        blockers.append("CONSENSUS_DUPLICATE_SOURCE")
        return SourceConsensusDecision(ConsensusStatus.CONFLICTED, False, blockers, warnings, evidence)
    if len(fresh) < min_sources:
        warnings.append("CONSENSUS_INSUFFICIENT_INDEPENDENT_SOURCES")
        return SourceConsensusDecision(ConsensusStatus.DEGRADED, False, blockers, warnings, evidence)

    prices = [item.last_price for item in fresh]
    midpoint = sum(prices) / len(prices)
    deviation = ((max(prices) - min(prices)) / midpoint * 100) if midpoint else float("inf")
    evidence["consensus_price"] = round(midpoint, 6)
    evidence["observed_deviation_pct"] = round(deviation, 6)
    if deviation > max_price_deviation_pct:
        blockers.append("CONSENSUS_PRICE_CONFLICT")
        return SourceConsensusDecision(ConsensusStatus.CONFLICTED, False, blockers, warnings, evidence)
    return SourceConsensusDecision(ConsensusStatus.VERIFIED, True, blockers, warnings, evidence)
