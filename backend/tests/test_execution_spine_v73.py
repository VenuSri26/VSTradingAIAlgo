from __future__ import annotations

import importlib

import pytest


class FakeBroker:
    def __init__(self, *, submit_error: Exception | None = None):
        self.submit_error = submit_error
        self.submissions = 0
        self.orders: list[dict] = []

    def place_buy_once(self, order, broker_tag):
        self.submissions += 1
        if self.submit_error:
            raise self.submit_error
        broker_order = {
            "order_id": "KITE-1",
            "tag": broker_tag,
            "tradingsymbol": order["tradingsymbol"],
            "transaction_type": "BUY",
            "quantity": order["quantity"],
            "filled_quantity": 0,
            "average_price": 0,
            "status": "OPEN",
        }
        self.orders.append(broker_order)
        return "KITE-1"

    def find_order_by_tag(self, *, broker_tag, order):
        matches = [o for o in self.orders if o["tag"] == broker_tag]
        return matches[0] if matches else None


class FakeDataSource:
    def __init__(self, symbol="NIFTY26SEP25000CE"):
        self.symbol = symbol

    def get_option_chain(self, atm_range=20):
        return {
            "chain": {
                "CE": [{
                    "tradingsymbol": self.symbol,
                    "bid": 99.5,
                    "ask": 100.0,
                    "volume": 1000,
                    "lot_size": 65,
                    "quote_timestamp": None,
                }],
                "PE": [],
            }
        }


def _prepare(monkeypatch, tmp_path):
    from app import store
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "vst.db"))
    from app import execution_ledger
    importlib.reload(execution_ledger)
    return execution_ledger


def _seed_preview_and_order(monkeypatch, tmp_path, live=True):
    _prepare(monkeypatch, tmp_path)
    from app import execution_readiness
    importlib.reload(execution_readiness)
    monkeypatch.setattr(execution_readiness, "risk_status", lambda: {"blocked": False, "kill_switch": False})
    monkeypatch.setattr(execution_readiness.store, "get_trade_setup", lambda setup_id: {
        "id": setup_id, "status": "APPROVED", "grade": "A+", "option_type": "CE"
    })
    preview = execution_readiness.create_preview({
        "tradingsymbol": "NIFTY26SEP25000CE",
        "transaction_type": "BUY",
        "quantity": 65,
        "order_type": "MARKET",
        "product": "MIS",
        "estimated_price": 100.0,
        "setup_id": 42,
        "idempotency_key": "test-signal-1",
    }, capital=100000, max_utilization_pct=50, lot_size=65)
    order = execution_readiness.confirm(preview["preview_id"], "CONFIRM", live)
    return preview, order


def test_preview_blocks_sell(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    from app import execution_readiness
    importlib.reload(execution_readiness)
    preview = execution_readiness.create_preview({
        "tradingsymbol": "NIFTY26SEP25000CE", "transaction_type": "SELL",
        "quantity": 65, "estimated_price": 100,
    }, 100000, 50, 65)
    assert preview["approved"] is False
    assert any(c["name"] == "buy_to_open_only" and not c["passed"] for c in preview["checks"])


def test_durable_duplicate_is_blocked(monkeypatch, tmp_path):
    preview, order = _seed_preview_and_order(monkeypatch, tmp_path, live=False)
    from app import execution_readiness
    # Simulate module restart: in-memory state no longer matters.
    importlib.reload(execution_readiness)
    with pytest.raises(ValueError, match="durable idempotency"):
        execution_readiness.confirm(preview["preview_id"], "CONFIRM", False)


def test_ambiguous_submit_becomes_unknown_and_is_not_retried(monkeypatch, tmp_path):
    _, order = _seed_preview_and_order(monkeypatch, tmp_path, live=True)
    from app import execution_spine
    importlib.reload(execution_spine)
    monkeypatch.setattr(execution_spine, "risk_status", lambda: {"blocked": False, "kill_switch": False})
    monkeypatch.setattr(execution_spine.store, "get_trade_setup", lambda setup_id: {
        "id": setup_id, "status": "APPROVED", "grade": "A+", "option_type": "CE"
    })
    monkeypatch.setattr(execution_spine.store, "get_open_position", lambda: None)
    monkeypatch.setattr(execution_spine.store, "get_open_paper_trade", lambda: None)
    class GoodQuality:
        approved = True
        blockers = []
        def to_dict(self): return {"approved": True, "blockers": []}
    monkeypatch.setattr(execution_spine, "current_live_data_quality", lambda: GoodQuality())
    monkeypatch.setattr(execution_spine, "evaluate_order_quote", lambda *a, **k: GoodQuality())

    broker = FakeBroker(submit_error=TimeoutError("response lost"))
    result = execution_spine.submit_once(
        order["execution_id"], broker=broker, data_source=FakeDataSource(),
        live_enabled=True, confirmation_text="EXECUTE LIVE",
    )
    assert result["status"] == "UNKNOWN"
    assert broker.submissions == 1
    with pytest.raises(ValueError, match="blind retry is forbidden"):
        execution_spine.submit_once(
            order["execution_id"], broker=broker, data_source=FakeDataSource(),
            live_enabled=True, confirmation_text="EXECUTE LIVE",
        )
    assert broker.submissions == 1


def test_unknown_reconciles_to_existing_broker_order(monkeypatch, tmp_path):
    _, order = _seed_preview_and_order(monkeypatch, tmp_path, live=True)
    from app import execution_spine
    importlib.reload(execution_spine)
    from app.execution_ledger import transition_order
    transition_order(order["execution_id"], "UNKNOWN", submitted_to_broker=True)
    broker = FakeBroker()
    broker.orders.append({
        "order_id": "KITE-77", "tag": order["broker_tag"],
        "tradingsymbol": order["order"]["tradingsymbol"],
        "transaction_type": "BUY", "quantity": 65, "filled_quantity": 65,
        "average_price": 101.25, "status": "COMPLETE",
    })
    result = execution_spine.reconcile_once(order["execution_id"], broker=broker)
    assert result["status"] == "COMPLETE"
    assert result["broker_order_id"] == "KITE-77"
    assert result["filled_quantity"] == 65
