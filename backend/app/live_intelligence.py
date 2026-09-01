from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any


def _legs(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    chain = snapshot.get("chain") or {}
    result: list[dict[str, Any]] = []
    for option_type in ("CE", "PE"):
        for leg in chain.get(option_type, []) or []:
            if isinstance(leg, dict):
                result.append({**leg, "option_type": option_type})
    return result


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _max_pain(snapshot: dict[str, Any]) -> int | None:
    legs = _legs(snapshot)
    strikes = sorted({int(_num(x.get("strike"))) for x in legs if _num(x.get("strike")) > 0})
    if not strikes:
        return None
    loss_by_strike: dict[int, float] = {}
    for settlement in strikes:
        total = 0.0
        for leg in legs:
            strike = int(_num(leg.get("strike")))
            oi = _num(leg.get("oi"))
            if leg["option_type"] == "CE":
                total += max(0, settlement - strike) * oi
            else:
                total += max(0, strike - settlement) * oi
        loss_by_strike[settlement] = total
    return min(loss_by_strike, key=loss_by_strike.get)


def analyse_live_market(snapshot: dict[str, Any], *, max_age_sec: int = 30) -> dict[str, Any]:
    """Normalize and validate a broker option-chain snapshot.

    The function is intentionally deterministic and broker-agnostic so it can
    be tested offline. It never authorizes execution; it only reports readiness.
    """
    legs = _legs(snapshot)
    now = datetime.now(timezone.utc)
    warnings: list[str] = []
    blockers: list[str] = []

    ts_raw = snapshot.get("timestamp") or snapshot.get("captured_at")
    age_sec: float | None = None
    if ts_raw:
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_sec = max(0.0, (now - ts.astimezone(timezone.utc)).total_seconds())
        except ValueError:
            warnings.append("Invalid snapshot timestamp")
    else:
        blockers.append("Snapshot timestamp is missing")

    if age_sec is not None and age_sec > max_age_sec:
        blockers.append(f"Snapshot is stale ({round(age_sec, 1)}s old)")
    if not legs:
        blockers.append("Option chain is empty")

    ce = [x for x in legs if x["option_type"] == "CE"]
    pe = [x for x in legs if x["option_type"] == "PE"]
    ce_oi = sum(_num(x.get("oi")) for x in ce)
    pe_oi = sum(_num(x.get("oi")) for x in pe)
    pcr = round(pe_oi / ce_oi, 4) if ce_oi > 0 else None

    ce_wall = max(ce, key=lambda x: _num(x.get("oi")), default=None)
    pe_wall = max(pe, key=lambda x: _num(x.get("oi")), default=None)
    ltp_values = [_num(x.get("ltp")) for x in legs if _num(x.get("ltp")) > 0]
    if ltp_values:
        med = median(ltp_values)
        outliers = [x for x in ltp_values if med > 0 and x > med * 20]
        if outliers:
            warnings.append(f"Detected {len(outliers)} extreme option-price outlier(s)")

    spot = _num(snapshot.get("spot") or snapshot.get("nifty_spot"))
    strikes = sorted({int(_num(x.get("strike"))) for x in legs if _num(x.get("strike")) > 0})
    atm = min(strikes, key=lambda x: abs(x - spot)) if strikes and spot else None
    if spot <= 0:
        blockers.append("Nifty spot is unavailable")

    completeness = 0
    expected_fields = ("strike", "oi", "ltp")
    if legs:
        complete = sum(1 for leg in legs if all(leg.get(k) is not None for k in expected_fields))
        completeness = round(complete / len(legs) * 100)
        if completeness < 80:
            warnings.append(f"Option-chain completeness is only {completeness}%")

    score = 100
    score -= len(blockers) * 30
    score -= len(warnings) * 8
    score = max(0, min(100, score))
    status = "BLOCKED" if blockers else "READY" if score >= 80 else "DEGRADED"

    return {
        "status": status,
        "readiness_score": score,
        "execution_mode": "DECISION_SUPPORT_ONLY",
        "live_orders_enabled": False,
        "captured_at": ts_raw,
        "age_sec": None if age_sec is None else round(age_sec, 2),
        "spot": spot or None,
        "atm_strike": atm,
        "expiry": snapshot.get("expiry"),
        "contracts": len(legs),
        "completeness_pct": completeness,
        "total_ce_oi": round(ce_oi, 2),
        "total_pe_oi": round(pe_oi, 2),
        "pcr_oi": pcr,
        "call_wall": int(_num(ce_wall.get("strike"))) if ce_wall else None,
        "put_wall": int(_num(pe_wall.get("strike"))) if pe_wall else None,
        "max_pain": _max_pain(snapshot),
        "warnings": warnings,
        "blockers": blockers,
        "recommended_action": "USE_FOR_DECISION_SUPPORT" if status == "READY" else "NO_TRADE",
    }
