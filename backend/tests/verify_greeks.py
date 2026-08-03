import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from app.greeks import compute_greeks, implied_volatility, enrich_chain_with_greeks, backend_name, _bs_price

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1; print(f"PASS  {name}")
    else:
        failed += 1; print(f"FAIL  {name}")

print(f"Backend: {backend_name()}\n")

S, r, sigma, t = 25300.0, 0.065, 0.15, 5 / 365  # 5 days to expiry, 15% IV, ~6.5% rate

# ATM call delta should be roughly 0.5 (slightly above due to drift term)
atm_call = compute_greeks("c", S, S, t, r, sigma)
check("atm_call_delta_near_half", 0.48 < atm_call["delta"] < 0.58)

# ATM put delta should be roughly -0.5
atm_put = compute_greeks("p", S, S, t, r, sigma)
check("atm_put_delta_near_neg_half", -0.52 < atm_put["delta"] < -0.42)

# gamma must be identical for call and put at the same strike (textbook BS property)
check("gamma_equal_for_call_and_put", abs(atm_call["gamma"] - atm_put["gamma"]) < 1e-9)

# gamma must be positive (long options always have positive gamma)
check("gamma_positive", atm_call["gamma"] > 0)

# vega must be positive and identical for call/put at same strike
check("vega_positive", atm_call["vega"] > 0)
check("vega_equal_for_call_and_put", abs(atm_call["vega"] - atm_put["vega"]) < 1e-6)

# deep ITM call delta should approach 1, deep OTM call delta should approach 0
deep_itm_call = compute_greeks("c", S, S - 2000, t, r, sigma)
deep_otm_call = compute_greeks("c", S, S + 2000, t, r, sigma)
check("deep_itm_call_delta_near_one", deep_itm_call["delta"] > 0.95)
check("deep_otm_call_delta_near_zero", deep_otm_call["delta"] < 0.05)

# put-call parity: C - P = S - K*exp(-rt)
call_price = _bs_price("c", S, S, t, r, sigma)
put_price = _bs_price("p", S, S, t, r, sigma)
parity_lhs = call_price - put_price
parity_rhs = S - S * np.exp(-r * t)
check("put_call_parity_holds", abs(parity_lhs - parity_rhs) < 0.01)

# IV round-trip: price an option, then solve IV back from that price
true_sigma = 0.18
priced = _bs_price("c", S, S + 100, t, r, true_sigma)
recovered_iv = implied_volatility(priced, "c", S, S + 100, t, r)
check("iv_roundtrip_accurate", recovered_iv is not None and abs(recovered_iv - true_sigma) < 0.001)

# price below intrinsic value should return None, not a fabricated IV
intrinsic = S - (S - 500)  # deep ITM call, intrinsic = 500
bad_price = intrinsic - 50  # below intrinsic - impossible market price
iv_bad = implied_volatility(bad_price, "c", S, S - 500, t, r)
check("below_intrinsic_returns_none", iv_bad is None)

# zero/negative price handled without crashing
check("zero_price_returns_none", implied_volatility(0, "c", S, S, t, r) is None)

# REGRESSION: the floor check must use the discounted forward intrinsic
# (S - K*exp(-rt)), not naive S-K. With r>0 these differ meaningfully for
# short-dated ITM options — using naive S-K as the floor would let prices
# through that are actually below the true Black-Scholes minimum (and
# conversely could reject valid prices sitting between the two floors).
from app.greeks import _theoretical_min_price
S2, K2, t2, r2 = 25323.145389024132, 25300, 2.25 / 365, 0.065
naive_floor = max(0.0, S2 - K2)
discounted_floor = _theoretical_min_price("c", S2, K2, t2, r2)
check("discounted_floor_exceeds_naive_floor", discounted_floor > naive_floor)

# a price consistent with the discounted floor (produced via round-trip
# from a real sigma, same as iv_roundtrip_accurate) must still solve
consistent_price = _bs_price("c", S2, K2, t2, r2, 0.12)
check("price_above_discounted_floor_solves", consistent_price > discounted_floor)
iv_check = implied_volatility(consistent_price, "c", S2, K2, t2, r2)
check("consistent_price_iv_solves", iv_check is not None and abs(iv_check - 0.12) < 0.001)

# a price that's realistic under naive S-K but actually below the true
# no-arbitrage floor (this can happen with heuristic/mock pricing) must be
# correctly rejected rather than fabricating a nonsense negative-vol result
below_true_floor_price = 28.70  # sits between naive floor (23.15) and true floor (33.28) here
check("naive_floor_confirms_arbitrage_gap", naive_floor < below_true_floor_price < discounted_floor)
iv_rejected = implied_volatility(below_true_floor_price, "c", S2, K2, t2, r2)
check("arbitrage_inconsistent_price_correctly_rejected", iv_rejected is None)

# chain enrichment: realistic mock chain gets real greeks attached
mock_chain = {
    "CE": [{"strike": 25300, "ltp": 110.0}, {"strike": 25350, "ltp": 85.0}],
    "PE": [{"strike": 25300, "ltp": 95.0}, {"strike": 25250, "ltp": 70.0}],
}
enriched = enrich_chain_with_greeks(mock_chain, spot=25300.0, days_to_expiry=5)
ce_atm = enriched["CE"][0]
check("chain_enrichment_adds_delta", ce_atm["delta"] is not None)
check("chain_enrichment_adds_iv", ce_atm["iv"] is not None and ce_atm["iv"] > 0)
check("chain_ce_delta_positive", ce_atm["delta"] > 0)
pe_atm = enriched["PE"][0]
check("chain_pe_delta_negative", pe_atm["delta"] < 0)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
