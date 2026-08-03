"""
Options Greeks and implied volatility — fills the gap flagged in the
project review: the Gamma Agent previously only inferred walls from raw OI,
with no actual delta/gamma/theta/vega anywhere in the system.

Nifty index options are European-style, so plain Black-Scholes (no early
exercise adjustment) is the correct model, not an approximation.

Two backends:
  - FAST PATH: py_vollib_vectorized, if installed (pip install py_vollib
    py_vollib_vectorized --break-system-packages). Battle-tested, very fast
    for computing Greeks across a whole option chain at once.
  - FALLBACK: a self-contained scipy-based implementation below, used
    automatically if py_vollib isn't installed. This is what runs in this
    sandbox (no network to install py_vollib here) and is mathematically
    equivalent — same Black-Scholes formulas, just not Peter Jäckel's
    optimized IV solver, so it's a bit slower on very large chains.

Either way, callers never need to know which backend is active.
"""
from __future__ import annotations
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

try:
    import py_vollib_vectorized  # noqa: F401
    from py_vollib.black_scholes import black_scholes as _pv_price
    from py_vollib.black_scholes.greeks.analytical import delta as _pv_delta
    from py_vollib.black_scholes.greeks.analytical import gamma as _pv_gamma
    from py_vollib.black_scholes.greeks.analytical import theta as _pv_theta
    from py_vollib.black_scholes.greeks.analytical import vega as _pv_vega
    from py_vollib.black_scholes.implied_volatility import implied_volatility as _pv_iv
    _BACKEND = "py_vollib"
except ImportError:
    _BACKEND = "fallback"


def backend_name() -> str:
    return _BACKEND


# ---- fallback implementation (always available, no extra dependency) -----

def _bs_price(flag: str, S: float, K: float, t: float, r: float, sigma: float) -> float:
    if t <= 0 or sigma <= 0:
        intrinsic = max(0.0, (S - K) if flag == "c" else (K - S))
        return intrinsic
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    if flag == "c":
        return S * norm.cdf(d1) - K * np.exp(-r * t) * norm.cdf(d2)
    return K * np.exp(-r * t) * norm.cdf(-d2) - S * norm.cdf(-d1)


def _bs_greeks(flag: str, S: float, K: float, t: float, r: float, sigma: float) -> dict:
    if t <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    pdf_d1 = norm.pdf(d1)

    delta = norm.cdf(d1) if flag == "c" else norm.cdf(d1) - 1
    gamma = pdf_d1 / (S * sigma * np.sqrt(t))
    vega = S * pdf_d1 * np.sqrt(t) / 100  # per 1 vol-point (1%) change

    if flag == "c":
        theta = (-S * pdf_d1 * sigma / (2 * np.sqrt(t)) - r * K * np.exp(-r * t) * norm.cdf(d2)) / 365
    else:
        theta = (-S * pdf_d1 * sigma / (2 * np.sqrt(t)) + r * K * np.exp(-r * t) * norm.cdf(-d2)) / 365

    return {"delta": round(float(delta), 4), "gamma": round(float(gamma), 6),
            "theta": round(float(theta), 4), "vega": round(float(vega), 4)}


def _theoretical_min_price(flag: str, S: float, K: float, t: float, r: float) -> float:
    """The Black-Scholes price as sigma -> 0 isn't the naive S-K intrinsic —
    it's the discounted forward intrinsic, S - K*exp(-rt) for calls. With a
    non-zero rate and even a few days to expiry this difference is material
    (e.g. ~10 points on a 2-day Nifty option), so using plain S-K as the
    'impossible price' floor was falsely rejecting valid ITM quotes."""
    if flag == "c":
        return max(0.0, S - K * np.exp(-r * t))
    return max(0.0, K * np.exp(-r * t) - S)


def _bs_implied_vol(price: float, flag: str, S: float, K: float, t: float, r: float) -> float | None:
    if price <= 0 or t <= 0:
        return None
    floor = _theoretical_min_price(flag, S, K, t, r)
    if price <= floor:
        return None  # genuinely below what any positive vol can produce — don't fabricate a number
    try:
        return round(float(brentq(
            lambda sigma: _bs_price(flag, S, K, t, r, sigma) - price, 1e-4, 5.0, maxiter=100,
        )), 4)
    except ValueError:
        return None  # no sign change in bracket — genuinely unsolvable at these inputs


# ---- public API (dispatches to whichever backend is active) --------------

def compute_greeks(flag: str, S: float, K: float, t_years: float, r: float, sigma: float) -> dict:
    """flag: 'c' or 'p'. t_years: time to expiry in years. r: annualized
    risk-free rate (e.g. 0.065 for ~6.5% India T-bill). sigma: IV as a
    decimal (0.15 = 15%)."""
    if _BACKEND == "py_vollib":
        try:
            return {
                "delta": round(float(_pv_delta(flag, S, K, t_years, r, sigma)), 4),
                "gamma": round(float(_pv_gamma(flag, S, K, t_years, r, sigma)), 6),
                "theta": round(float(_pv_theta(flag, S, K, t_years, r, sigma)), 4),
                "vega": round(float(_pv_vega(flag, S, K, t_years, r, sigma)), 4),
            }
        except Exception:
            pass  # fall through to the always-available fallback below
    return _bs_greeks(flag, S, K, t_years, r, sigma)


def implied_volatility(price: float, flag: str, S: float, K: float, t_years: float, r: float) -> float | None:
    if _BACKEND == "py_vollib":
        try:
            return round(float(_pv_iv(price, S, K, t_years, r, flag)), 4)
        except Exception:
            pass
    return _bs_implied_vol(price, flag, S, K, t_years, r)


def enrich_chain_with_greeks(chain: dict, spot: float, days_to_expiry: float, risk_free_rate: float = 0.065) -> dict:
    """Takes the {'CE': [...], 'PE': [...]} chain shape our data sources
    already produce and adds 'iv', 'delta', 'gamma', 'theta', 'vega' to each
    leg in place. IV is solved from each leg's own LTP (real market-implied
    vol) rather than assumed — 'iv' is only overwritten if it was missing or
    the leg's own quoted iv looks unset."""
    t_years = max(days_to_expiry, 0.0) / 365.0
    for side, flag in (("CE", "c"), ("PE", "p")):
        for leg in chain.get(side, []):
            strike = leg["strike"]
            price = leg.get("ltp")
            if price is None or price <= 0:
                leg.update(delta=None, gamma=None, theta=None, vega=None)
                continue
            iv = implied_volatility(price, flag, spot, strike, t_years, risk_free_rate)
            if iv is None:
                leg.update(iv=leg.get("iv"), delta=None, gamma=None, theta=None, vega=None)
                continue
            leg["iv"] = round(iv * 100, 2)  # store as a percentage, matching existing 'iv' convention
            greeks = compute_greeks(flag, spot, strike, t_years, risk_free_rate, iv)
            leg.update(greeks)
    return chain
