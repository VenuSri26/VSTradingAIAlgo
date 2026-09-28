from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app import store
from app.config import settings
from app.live_intelligence import analyse_live_market
from app.version import APP_VERSION

REQUIRED_CONFIRMATION_TEXT = "PREPARE_PAPER_SETUP"


class PaperSetupNotReady(RuntimeError):
    """Raised when a preview result isn't READY_FOR_HUMAN_REVIEW.

    Carries the full preview `result` dict so the route layer can surface it
    unchanged (e.g. as the body of an HTTP 409) without this module knowing
    anything about HTTP.
    """

    def __init__(self, result: dict[str, Any]):
        super().__init__(str(result.get("status", "NOT_READY")))
        self.result = result


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

    if leg is not None:
        bid = _num(leg.get("bid"))
        ask = _num(leg.get("ask"))
        oi = _num(leg.get("oi"))
        volume = _num(leg.get("volume"))
        if bid <= 0 or ask <= 0 or ask < bid:
            blockers.append("Selected option has no valid two-sided bid/ask quote")
        else:
            mid = (bid + ask) / 2
            spread_pct = (ask - bid) / mid * 100 if mid > 0 else 999.0
            if spread_pct > settings.paper_max_option_spread_pct:
                blockers.append(
                    f"Selected option spread {spread_pct:.2f}% exceeds "
                    f"{settings.paper_max_option_spread_pct:.2f}%"
                )
        if oi < settings.paper_min_option_oi:
            blockers.append(
                f"Selected option OI {oi:.0f} is below {settings.paper_min_option_oi}"
            )
        if volume < settings.paper_min_option_volume:
            blockers.append(
                f"Selected option volume {volume:.0f} is below {settings.paper_min_option_volume}"
            )

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

    # A paper BUY fills from the ask side, not the optimistic last-traded
    # price. The configured slippage is applied later by the paper ledger.
    entry = round(_num(leg.get("ask")), 2)
    strike = int(_num(leg.get("strike")))
    stop_loss = round(entry * (1 - settings.paper_default_stop_loss_pct / 100), 2)
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
        "strategy_version": APP_VERSION,
    }
    reproducibility_record = {
        "candidate": candidate,
        "input_snapshot": snapshot,
        "strategy_version": APP_VERSION,
    }
    signature = hashlib.sha256(
        json.dumps(reproducibility_record, sort_keys=True, default=str).encode()
    ).hexdigest()
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
        "input_snapshot": snapshot,
        "strategy_version": APP_VERSION,
    }


def build_paper_setup_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Pure transform: a READY_FOR_HUMAN_REVIEW preview result -> the payload
    shape `app.store.create_trade_setup` expects."""
    c = result["candidate"]
    return {
        "timestamp": c["captured_at"],
        "decision": {
            "decision": c["decision"],
            "grade": c["grade"],
            "alignment_score": c["alignment_score"],
            "explanation": "; ".join(c["rationale"]),
            "plan": {
                "option_type": c["option_type"], "strike": c["strike"],
                "entry_low": c["entry_low"], "entry_high": c["entry_high"],
                "stop_loss": c["stop_loss"], "target_1": c["target_1"],
                "target_2": c["target_2"], "risk_reward": c["risk_reward"],
            },
        },
        "live_intelligence": result["intelligence"],
        "live_trend": result["trend"],
        "finalized_candle": result.get("finalized_candle"),
        "input_snapshot": result.get("input_snapshot"),
        "strategy_version": result.get("strategy_version") or c.get("strategy_version"),
        "full_pipeline": result.get("full_pipeline"),
        "source": "LIVE_PAPER_BRIDGE",
        "execution_mode": "PAPER_ONLY",
    }


def validate_confirmation_text(confirmation_text: str) -> None:
    """Raises ValueError with the user-facing message if the typed
    confirmation phrase doesn't match. Deliberately cheap and side-effect
    free so the route can call it before paying for a live data-source
    fetch, exactly like the original inline check did."""
    if confirmation_text != REQUIRED_CONFIRMATION_TEXT:
        raise ValueError(f"Type {REQUIRED_CONFIRMATION_TEXT} to create a draft")


def prepare_paper_setup_from_preview(result: dict[str, Any]) -> dict[str, Any]:
    """Framework-free core of `POST /api/live-paper/prepare`, for the part
    that runs after a preview has already been computed:

    - Requires the preview to be READY_FOR_HUMAN_REVIEW (raises
      PaperSetupNotReady, carrying the preview result, otherwise).
    - Creates the PAPER-only trade setup, or returns the existing one if this
      exact candidate signature was already created (dedup).

    The route layer's only job is to call `validate_confirmation_text` first,
    then map PaperSetupNotReady to the right HTTP status; all the actual
    business logic lives here so it can be unit tested without a running
    FastAPI app.
    """
    if result.get("status") != "READY_FOR_HUMAN_REVIEW":
        raise PaperSetupNotReady(result)

    payload = build_paper_setup_payload(result)
    setup_id = store.create_trade_setup(result["signature"], payload)
    if setup_id is None:
        matches = store.list_trade_setups(limit=20)
        existing = next((x for x in matches if x.get("signature") == result["signature"]), None)
        return {"created": False, "reason": "DUPLICATE", "setup": existing, **result}
    setup = store.get_trade_setup(setup_id)
    return {"created": True, "setup": setup, **result}
