"""Compares broker-reported option Greeks with local Black-Scholes values."""
from __future__ import annotations
from typing import Any
from app.greeks import compute_greeks, implied_volatility, backend_name


def compare_broker_greeks(payload: dict[str, Any]) -> dict[str, Any]:
    side = str(payload.get("option_type") or "CE").upper()
    flag = "c" if side == "CE" else "p"
    spot = float(payload["spot"]); strike = float(payload["strike"]); ltp = float(payload["ltp"])
    days = max(0.0, float(payload.get("days_to_expiry", 0.0)))
    rate = float(payload.get("risk_free_rate", 0.065))
    broker = payload.get("broker_greeks") or {}
    iv_pct = payload.get("broker_iv")
    iv = float(iv_pct) / 100.0 if iv_pct not in (None, "") else implied_volatility(ltp, flag, spot, strike, days / 365.0, rate)
    if iv is None or iv <= 0:
        return {"status": "BLOCKED", "reason": "IMPLIED_VOLATILITY_UNAVAILABLE", "live_orders_enabled": False}
    model = compute_greeks(flag, spot, strike, days / 365.0, rate, iv)
    tolerances = {"delta": 0.08, "gamma": 0.002, "theta": 3.0, "vega": 3.0}
    comparisons = []
    for key, tolerance in tolerances.items():
        broker_value = broker.get(key)
        if broker_value is None:
            comparisons.append({"metric": key, "status": "NOT_PROVIDED", "model": model[key], "broker": None, "difference": None})
            continue
        difference = abs(float(broker_value) - float(model[key]))
        comparisons.append({"metric": key, "status": "PASS" if difference <= tolerance else "FAIL",
                            "model": model[key], "broker": float(broker_value),
                            "difference": round(difference, 6), "tolerance": tolerance})
    provided = [x for x in comparisons if x["status"] != "NOT_PROVIDED"]
    failed = [x for x in provided if x["status"] == "FAIL"]
    return {"status": "PASS" if provided and not failed else ("WARNING" if not provided else "FAIL"),
            "option_type": side, "spot": spot, "strike": strike, "ltp": ltp,
            "iv_pct": round(iv * 100, 4), "backend": backend_name(), "model_greeks": model,
            "comparisons": comparisons, "provided_metrics": len(provided), "failed_metrics": len(failed),
            "recommended_action": "USE_FOR_DECISION_SUPPORT" if provided and not failed else "REVIEW_GREEKS_SOURCE",
            "live_orders_enabled": False}
