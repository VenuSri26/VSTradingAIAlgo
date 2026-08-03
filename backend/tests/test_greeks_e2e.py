import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["AUDIT_LOG_PATH"] = "/tmp/greeks_e2e_audit.jsonl"
os.environ["SQLITE_DB_PATH"] = "/tmp/greeks_e2e_store.db"
from app.data_sources.mock_source import MockDataSource
from app.pipeline import run_pipeline

resp = run_pipeline(MockDataSource(seed=5))

chain = resp.options["snapshot"]["chain"]
all_legs = chain["CE"] + chain["PE"]
legs_with_delta = [leg for leg in all_legs if leg.get("delta") is not None]
print(f"Legs with Greeks: {len(legs_with_delta)}/{len(all_legs)}")
for leg in all_legs:
    print(f"  {leg['strike']}: ltp={leg['ltp']} delta={leg.get('delta')} gamma={leg.get('gamma')} iv={leg.get('iv')}")

print("\nGamma dict:", resp.gamma)

print("\nSystem health components:")
for c in resp.system_health.components:
    print(f"  {c.name}: {c.status.value} - {c.detail}")

print("\nDecision:", resp.decision.decision.value, resp.decision.grade.value)
if resp.decision.plan:
    print("Plan delta/theta/iv:", resp.decision.plan.delta, resp.decision.plan.theta, resp.decision.plan.iv)

# The mock generator prices legs with simple heuristics, not Black-Scholes,
# so an occasional leg can land below the true no-arbitrage floor — Greeks
# correctly reports those as unavailable rather than fabricating a result
# (see tests/test_greeks.py::arbitrage_inconsistent_price_correctly_rejected).
# What matters is that MOST legs solve successfully, proving the pipeline
# wiring itself works end-to-end.
assert len(legs_with_delta) >= len(all_legs) * 0.6, f"too few legs got Greeks: {len(legs_with_delta)}/{len(all_legs)}"
sample = legs_with_delta[0]
assert -1 <= sample["delta"] <= 1, "delta out of valid range"
assert sample["gamma"] >= 0, "gamma should be non-negative"
assert resp.gamma.get("net_gex") is not None, "net GEX should be computed"
print("\nAll assertions passed.")
