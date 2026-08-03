from __future__ import annotations
from datetime import datetime, timezone
from math import isfinite
from typing import Any
from app.greeks import enrich_chain_with_greeks, backend_name


def _days_to_expiry(expiry: str | None) -> float:
    if not expiry:
        return 1.0
    try:
        dt = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max((dt - datetime.now(timezone.utc)).total_seconds() / 86400.0, 1 / 24)
    except Exception:
        return 1.0


def analyse_gamma(snapshot: dict[str, Any], lot_size: int = 75) -> dict[str, Any]:
    spot = float(snapshot.get("spot") or snapshot.get("atm") or 0.0)
    chain = snapshot.get("chain") or {"CE": [], "PE": []}
    if not spot or not chain.get("CE") or not chain.get("PE"):
        return {"dealer_regime": "UNKNOWN", "net_gex": 0.0, "gamma_flip": None, "call_gamma_wall": None, "put_gamma_wall": None, "confidence": 0.0, "warnings": ["Incomplete option chain"]}
    enrich_chain_with_greeks(chain, spot, _days_to_expiry(snapshot.get("expiry")))
    rows: dict[float, dict[str, float]] = {}
    for side, sign in (("CE", 1.0), ("PE", -1.0)):
        for leg in chain.get(side, []):
            gamma = leg.get("gamma")
            oi = float(leg.get("oi") or 0.0)
            strike = float(leg.get("strike") or 0.0)
            if gamma is None or not strike:
                continue
            gex = float(gamma) * oi * lot_size * spot * spot * 0.01 * sign
            if not isfinite(gex):
                continue
            rows.setdefault(strike, {"call_gex": 0.0, "put_gex": 0.0, "net_gex": 0.0})
            if side == "CE": rows[strike]["call_gex"] += gex
            else: rows[strike]["put_gex"] += gex
            rows[strike]["net_gex"] += gex
    if not rows:
        return {"dealer_regime": "UNKNOWN", "net_gex": 0.0, "gamma_flip": None, "call_gamma_wall": None, "put_gamma_wall": None, "confidence": 10.0, "warnings": ["Greeks could not be solved"]}
    strikes = sorted(rows)
    net = sum(v["net_gex"] for v in rows.values())
    call_wall = max(strikes, key=lambda k: rows[k]["call_gex"])
    put_wall = min(strikes, key=lambda k: rows[k]["put_gex"])
    flip = None
    for left, right in zip(strikes, strikes[1:]):
        if rows[left]["net_gex"] == 0 or rows[left]["net_gex"] * rows[right]["net_gex"] < 0:
            flip = round((left + right) / 2, 2)
            break
    dealer_regime = "LONG_GAMMA" if net >= 0 else "SHORT_GAMMA"
    pinning = sorted(strikes, key=lambda k: abs(k - spot))[:3] if dealer_regime == "LONG_GAMMA" else []
    return {
        "dealer_regime": dealer_regime,
        "net_gex": round(net, 2),
        "gamma_flip": flip,
        "call_gamma_wall": call_wall,
        "put_gamma_wall": put_wall,
        "pinning_zone": pinning,
        "confidence": round(min(100.0, 45.0 + len(rows) * 3.0), 2),
        "backend": backend_name(),
        "strikes": [{"strike": k, **{n: round(v, 2) for n, v in rows[k].items()}} for k in strikes],
        "warnings": [],
    }
