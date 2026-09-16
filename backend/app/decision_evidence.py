"""Deterministic certificate binding a decision to one finalized 3-minute bar."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


def _digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def build_decision_evidence(candle: dict[str, Any], features: dict[str, Any]) -> dict[str, Any]:
    timestamp = str(candle.get("timestamp") or candle.get("end") or candle.get("start") or "")
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.minute % 3 != 0 or parsed.second != 0:
        raise ValueError("DecisionEvidence requires an exchange-aligned timezone-aware 3-minute bar")
    if candle.get("finalized") is not True:
        raise ValueError("DecisionEvidence requires a finalized bar")
    bar = {
        "bar_id": timestamp, "timeframe": "3m", "finalized": True,
        "open": float(candle["open"]), "high": float(candle["high"]),
        "low": float(candle["low"]), "close": float(candle["close"]),
        "volume": float(candle.get("volume") or 0),
        "tick_count": int(candle.get("ticks") or 0),
    }
    core = {"schema": "decision-evidence/v1", "bar": bar, "feature_hash": _digest(features)}
    return {**core, "evidence_hash": _digest(core)}


def verify_decision_evidence(evidence: dict[str, Any]) -> bool:
    supplied = str(evidence.get("evidence_hash") or "")
    core = {key: evidence.get(key) for key in ("schema", "bar", "feature_hash")}
    return bool(supplied) and evidence.get("schema") == "decision-evidence/v1" and _digest(core) == supplied
