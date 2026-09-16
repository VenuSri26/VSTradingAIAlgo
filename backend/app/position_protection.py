"""Deterministic position-protection evidence for long NIFTY options."""
from __future__ import annotations

from typing import Any

from app.config import settings


def validate_protection_plan(setup: dict[str, Any], order: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    try:
        entry_low = float(setup.get("entry_low") or 0)
        entry_high = float(setup.get("entry_high") or 0)
        stop = float(setup.get("stop_loss") or 0)
        target_1 = float(setup.get("target_1") or 0)
        target_2 = float(setup.get("target_2") or 0)
        risk_reward = float(setup.get("risk_reward") or 0)
    except (TypeError, ValueError):
        entry_low = entry_high = stop = target_1 = target_2 = risk_reward = 0

    if not (0 < stop < entry_low <= entry_high):
        blockers.append("INVALID_HARD_STOP_OR_ENTRY_RANGE")
    if not (target_1 > entry_high and target_2 >= target_1):
        blockers.append("INVALID_TARGET_LADDER")
    if risk_reward < float(settings.min_risk_reward):
        blockers.append("RISK_REWARD_BELOW_MINIMUM")
    if not str(setup.get("explanation") or "").strip():
        blockers.append("INVALIDATION_RATIONALE_MISSING")
    supplied_stop = order.get("stop_loss")
    if supplied_stop is not None and float(supplied_stop) != stop:
        blockers.append("STOP_OVERRIDE_FORBIDDEN")

    return {
        "approved": not blockers,
        "blockers": blockers,
        "policy": {
            "entry_low": entry_low, "entry_high": entry_high, "hard_stop": stop,
            "target_1": target_1, "target_2": target_2, "risk_reward": risk_reward,
            "stop_may_widen": False, "average_down": False,
        },
    }
