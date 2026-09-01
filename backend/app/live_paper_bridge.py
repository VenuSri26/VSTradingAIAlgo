from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.live_intelligence import analyse_live_market


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_paper_setup_candidate(
    snapshot: dict[str, Any],
    trend: dict[str, Any] | None = None,
    *,
    max_age_sec: int = 30,
) -> dict[str, Any]:
    """Build a human-reviewable paper setup from validated broker data.

    The bridge never approves, executes, or submits an order. It only prepares
    a deterministic DRAFT setup when the live-intelligence gate is READY and
    the intraday OI/PCR trend has a directional confirmation.
    """
    intelligence = analyse_live_market(snapshot, max_age_sec=max_age_sec)
    blockers = list(intelligence.get("blockers") or [])
    warnings = list(intelligence.get("warnings") or [])
    trend = trend or {}
    trend_label = str(trend.get("trend") or "NO_DATA")

    option_type: str | None = None
    if trend_label == "BULLISH_STRENGTHENING":
        option_type = "CE"
    elif trend_label == "BEARISH_STRENGTHENING":
        option_type = "PE"
    else:
        blockers.append(f"Directional OI/PCR trend is not confirmed ({trend_label})")

    if intelligence.get("status") != "READY":
        blockers.append("Live-intelligence quality gate is not READY")

    chain = snapshot.get("chain") or {}
    atm = intelligence.get("atm_strike")
    legs = chain.get(option_type, []) if option_type else []
    leg = min(
        (x for x in legs if isinstance(x, dict) and _num(x.get("ltp")) > 0),
        key=lambda x: abs(int(_num(x.get("strike"))) - int(atm or 0)),
        default=None,
    )
    if option_type and leg is None:
        blockers.append(f"No tradable {option_type} contract found near ATM")

    if blockers:
        return {
            "status": "BLOCKED",
            "action": "NO_TRADE",
            "execution_mode": "PAPER_PREVIEW_ONLY",
            "live_orders_enabled": False,
            "intelligence": intelligence,
            "trend": trend_label,
            "warnings": warnings,
            "blockers": list(dict.fromkeys(blockers)),
            "candidate": None,
        }

    entry = round(_num(leg.get("ltp")), 2)
    strike = int(_num(leg.get("strike")))
    stop_loss = round(entry * 0.80, 2)
    target_1 = round(entry * 1.30, 2)
    target_2 = round(entry * 1.50, 2)
    risk = max(0.01, entry - stop_loss)
    rr = round((target_1 - entry) / risk, 2)
    captured_at = snapshot.get("timestamp") or snapshot.get("captured_at") or datetime.now(timezone.utc).isoformat()
    rationale = [
        f"Live-intelligence gate READY at {intelligence.get('readiness_score')}/100",
        f"Intraday flow trend: {trend_label}",
        f"PCR: {intelligence.get('pcr_oi')}",
        f"ATM contract selected: {strike} {option_type}",
    ]
    candidate = {
        "decision": f"{option_type}_BUY",
        "grade": "A" if intelligence.get("readiness_score", 0) < 95 else "A+",
        "alignment_score": intelligence.get("readiness_score"),
        "option_type": option_type,
        "strike": strike,
        "entry_low": round(entry * 0.99, 2),
        "entry_high": round(entry * 1.01, 2),
        "entry_reference": entry,
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "risk_reward": rr,
        "captured_at": captured_at,
        "expiry": snapshot.get("expiry"),
        "rationale": rationale,
    }
    signature = hashlib.sha256(json.dumps(candidate, sort_keys=True).encode()).hexdigest()
    return {
        "status": "READY_FOR_HUMAN_REVIEW",
        "action": "PREPARE_PAPER_SETUP",
        "execution_mode": "PAPER_PREVIEW_ONLY",
        "live_orders_enabled": False,
        "signature": signature,
        "intelligence": intelligence,
        "trend": trend_label,
        "warnings": warnings,
        "blockers": [],
        "candidate": candidate,
    }
