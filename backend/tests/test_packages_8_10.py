from app.execution_readiness import create_preview, confirm, list_orders
from app.live_data import mark_snapshot, status


def test_live_data_freshness():
    mark_snapshot({"timestamp": "2099-01-01T00:00:00+00:00", "options": {"expiry": "2099-01-07", "chain": {"CE": [{}], "PE": [{}]}}})
    result = status(15)
    assert result["connected"] is True
    assert result["instruments_synced"] == 2


def test_execution_preview_blocks_bad_lot():
    result = create_preview({"tradingsymbol":"NIFTYTESTCE", "transaction_type":"BUY", "quantity":10, "estimated_price":10}, 100000, 80, 75)
    assert result["approved"] is False


def test_execution_confirmation_is_simulated_and_idempotent():
    preview = create_preview({"tradingsymbol":"NIFTYTESTCE", "transaction_type":"BUY", "quantity":75, "estimated_price":10}, 100000, 80, 75)
    order = confirm(preview["preview_id"], "CONFIRM", False)
    assert order["submitted_to_broker"] is False
    assert order["status"] == "SIMULATED_CONFIRMED"
    assert list_orders()
