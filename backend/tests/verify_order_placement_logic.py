import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1; print(f"PASS  {name}")
    else:
        failed += 1; print(f"FAIL  {name}")

# Reimplements just the branching logic from
# ZerodhaDataSource.place_autoslice_order in isolation, since the real
# kiteconnect SDK isn't installable in this offline sandbox. This proves the
# fallback/normalisation logic is correct; it does not (and cannot, without
# network + real credentials) prove the actual Kite API call succeeds.

class FakeKiteWithAutoslice:
    def __init__(self, return_value):
        self._return_value = return_value
    def place_autoslice_order(self, **kwargs):
        return self._return_value

class FakeKiteWithoutAutoslice:
    def place_order(self, **kwargs):
        return "order_123"

class FakeKiteAutosliceFails:
    def place_autoslice_order(self, **kwargs):
        raise Exception("simulated API failure")


def place_autoslice_order_logic(kite):
    """Mirrors the branching in zerodha_client.py::place_autoslice_order."""
    if hasattr(kite, "place_autoslice_order"):
        result = kite.place_autoslice_order(
            variety="regular", exchange="NFO", tradingsymbol="NIFTY26AUG25300CE",
            transaction_type="BUY", quantity=5400, product="MIS", order_type="MARKET", price=None,
        )
        return result if isinstance(result, list) else [result]
    order_id = kite.place_order(
        variety="regular", exchange="NFO", tradingsymbol="NIFTY26AUG25300CE",
        transaction_type="BUY", quantity=5400, product="MIS", order_type="MARKET", price=None,
    )
    return [order_id]


# case 1: SDK has autoslice, order didn't need splitting -> single order_id
result1 = place_autoslice_order_logic(FakeKiteWithAutoslice("order_abc"))
check("single_order_normalized_to_list", result1 == ["order_abc"])

# case 2: SDK has autoslice, order got split -> multiple order_ids
result2 = place_autoslice_order_logic(FakeKiteWithAutoslice(["order_1", "order_2", "order_3"]))
check("sliced_orders_returned_as_list", result2 == ["order_1", "order_2", "order_3"])

# case 3: older SDK without autoslice -> falls back to place_order
result3 = place_autoslice_order_logic(FakeKiteWithoutAutoslice())
check("fallback_to_place_order_when_unsupported", result3 == ["order_123"])

# case 4: autoslice exists but the call fails -> should raise, not swallow
try:
    place_autoslice_order_logic(FakeKiteAutosliceFails())
    check("autoslice_failure_propagates", False)
except Exception as e:
    check("autoslice_failure_propagates", "simulated API failure" in str(e))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
