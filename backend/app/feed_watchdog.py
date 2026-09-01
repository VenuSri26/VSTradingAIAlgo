from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.market_clock import market_clock, parse_timestamp


def _age_sec(timestamp: str | None, now: datetime) -> float | None:
    if not timestamp:
        return None
    try:
        return max(0.0, (now - parse_timestamp(timestamp)).total_seconds())
    except (ValueError, TypeError):
        return None


def evaluate_feed_safety(
    state: dict[str, Any],
    *,
    now: str | datetime | None = None,
    stale_after_sec: float = 15.0,
    holidays: str | list[str] | None = None,
    open_time: str = "09:15",
    close_time: str = "15:30",
    require_market_open: bool = True,
) -> dict[str, Any]:
    now_dt = parse_timestamp(now)
    clock = market_clock(now_dt, holidays=holidays, open_time=open_time, close_time=close_time)
    market_age = _age_sec(state.get("last_market_timestamp") or state.get("last_success_at"), now_dt)
    token_age = _age_sec(state.get("token_checked_at"), now_dt)
    blockers: list[str] = []
    warnings: list[str] = []

    if require_market_open and not clock.market_open:
        blockers.append(f"Market session is {clock.session}: {clock.reason}")
    if not state.get("authenticated"):
        blockers.append("Broker authentication is not healthy")
    if not state.get("connected"):
        blockers.append("Market feed is disconnected")
    if market_age is None:
        blockers.append("No exchange timestamp is available")
    elif market_age > stale_after_sec:
        blockers.append(f"Market data is stale ({market_age:.1f}s > {stale_after_sec:.1f}s)")
    if int(state.get("consecutive_failures") or 0) >= 3:
        blockers.append("Feed has three or more consecutive failures")
    elif int(state.get("consecutive_failures") or 0) > 0:
        warnings.append("Feed has recent failures")
    if state.get("websocket_requested") and not state.get("websocket_active"):
        warnings.append("WebSocket requested but REST fallback is active")
    if token_age is not None and token_age > 3600:
        warnings.append("Broker token health has not been checked in the last hour")
    if not state.get("expiry"):
        warnings.append("Current option expiry is unavailable")
    if int(state.get("instruments_synced") or 0) <= 0:
        warnings.append("Instrument master is not synchronized")

    score = 100
    score -= min(80, len(blockers) * 25)
    score -= min(20, len(warnings) * 5)
    score = max(0, score)
    status = "READY" if not blockers else "BLOCKED"
    action = "ALLOW_DECISION_SUPPORT" if status == "READY" else "NO_TRADE"

    return {
        "status": status,
        "score": score,
        "recommended_action": action,
        "market_clock": clock.to_dict(),
        "market_age_sec": round(market_age, 2) if market_age is not None else None,
        "token_check_age_sec": round(token_age, 2) if token_age is not None else None,
        "feed_mode": state.get("mode"),
        "websocket_requested": bool(state.get("websocket_requested")),
        "websocket_active": bool(state.get("websocket_active")),
        "rest_fallback_active": not bool(state.get("websocket_active")),
        "blockers": blockers,
        "warnings": warnings,
        "live_orders_enabled": False,
    }
