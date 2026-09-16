"""Evidence-based certification for promoting source consensus from shadow mode."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from math import ceil
from typing import Any, Iterable


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, ceil(0.95 * len(ordered)) - 1)]


def certify_consensus_shadow(
    rows: Iterable[dict[str, Any]], *, min_samples: int, min_sessions: int,
    min_verified_ratio: float, max_conflict_ratio: float, max_stale_ratio: float,
    max_p95_deviation_pct: float,
) -> dict[str, Any]:
    evidence = list(rows)
    counts = Counter(str(row.get("status") or "UNKNOWN") for row in evidence)
    total = len(evidence)
    sessions: set[str] = set()
    deviations: list[float] = []
    for row in evidence:
        timestamp = row.get("primary_exchange_timestamp") or row.get("recorded_at")
        try:
            sessions.add(datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).date().isoformat())
        except (TypeError, ValueError):
            pass
        if row.get("deviation_pct") is not None:
            deviations.append(float(row["deviation_pct"]))
    ratio = lambda key: counts.get(key, 0) / total if total else 0.0
    metrics = {
        "samples": total,
        "sessions": len(sessions),
        "verified_ratio": round(ratio("VERIFIED"), 6),
        "conflict_ratio": round(ratio("CONFLICTED"), 6),
        "stale_ratio": round(ratio("STALE"), 6),
        "p95_deviation_pct": round(_p95(deviations), 6) if deviations else None,
        "status_counts": dict(sorted(counts.items())),
    }
    thresholds = {
        "min_samples": min_samples, "min_sessions": min_sessions,
        "min_verified_ratio": min_verified_ratio, "max_conflict_ratio": max_conflict_ratio,
        "max_stale_ratio": max_stale_ratio, "max_p95_deviation_pct": max_p95_deviation_pct,
    }
    blockers: list[str] = []
    if total < min_samples: blockers.append("INSUFFICIENT_CONSENSUS_SAMPLES")
    if len(sessions) < min_sessions: blockers.append("INSUFFICIENT_CONSENSUS_SESSIONS")
    if ratio("VERIFIED") < min_verified_ratio: blockers.append("VERIFIED_RATIO_BELOW_THRESHOLD")
    if ratio("CONFLICTED") > max_conflict_ratio: blockers.append("CONFLICT_RATIO_ABOVE_THRESHOLD")
    if ratio("STALE") > max_stale_ratio: blockers.append("STALE_RATIO_ABOVE_THRESHOLD")
    p95 = _p95(deviations)
    if p95 is None: blockers.append("DEVIATION_EVIDENCE_UNAVAILABLE")
    elif p95 > max_p95_deviation_pct: blockers.append("P95_DEVIATION_ABOVE_THRESHOLD")
    return {
        "certified": not blockers,
        "mode": "EVIDENCE_ONLY",
        "metrics": metrics,
        "thresholds": thresholds,
        "blockers": blockers,
        "automatic_enforcement_change": False,
        "live_orders_enabled": False,
    }
