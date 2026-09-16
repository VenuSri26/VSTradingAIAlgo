from datetime import datetime
from zoneinfo import ZoneInfo

from app import execution_spine


class PositionBroker:
    def __init__(self, rows):
        self.rows = rows

    def positions(self):
        return {"net": self.rows}


def _local_order(quantity=65):
    return {
        "created_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(),
        "status": "COMPLETE",
        "filled_quantity": quantity,
        "order": {"tradingsymbol": "NIFTY99DEC25000CE"},
    }


def _broker_position(quantity=65, **overrides):
    row = {
        "exchange": "NFO",
        "tradingsymbol": "NIFTY99DEC25000CE",
        "quantity": quantity,
    }
    row.update(overrides)
    return row


def test_position_reconciliation_accepts_exact_broker_match(monkeypatch):
    events = []
    monkeypatch.setattr(execution_spine, "list_orders", lambda limit=500: [_local_order()])
    monkeypatch.setattr(execution_spine, "record_event", lambda execution_id, event, detail: events.append(event))
    monkeypatch.setattr(execution_spine.store, "set_kill_switch", lambda *args: (_ for _ in ()).throw(AssertionError("must not latch")))

    result = execution_spine.reconcile_positions_once(broker=PositionBroker([_broker_position()]))

    assert result["matched"] is True
    assert result["mismatches"] == []
    assert events == ["POSITION_RECONCILIATION_MATCHED"]


def test_position_reconciliation_latches_kill_switch_on_quantity_mismatch(monkeypatch):
    latched = []
    events = []
    monkeypatch.setattr(execution_spine, "list_orders", lambda limit=500: [_local_order()])
    monkeypatch.setattr(execution_spine.store, "set_kill_switch", lambda enabled, reason: latched.append((enabled, reason)))
    monkeypatch.setattr(execution_spine, "record_event", lambda execution_id, event, detail: events.append((event, detail)))

    result = execution_spine.reconcile_positions_once(broker=PositionBroker([_broker_position(130)]))

    assert result["matched"] is False
    assert result["mismatches"][0]["local_quantity"] == 65
    assert result["mismatches"][0]["broker_quantity"] == 130
    assert latched == [(True, "Broker/local NIFTY position mismatch")]
    assert events[0][0] == "POSITION_RECONCILIATION_MISMATCH"
    assert events[0][1]["kill_switch_latched"] is True


def test_position_reconciliation_blocks_unexpected_broker_position(monkeypatch):
    latched = []
    monkeypatch.setattr(execution_spine, "list_orders", lambda limit=500: [])
    monkeypatch.setattr(execution_spine.store, "set_kill_switch", lambda enabled, reason: latched.append(enabled))
    monkeypatch.setattr(execution_spine, "record_event", lambda *args: None)

    result = execution_spine.reconcile_positions_once(broker=PositionBroker([_broker_position()]))

    assert result["matched"] is False
    assert result["mismatches"] == [{
        "tradingsymbol": "NIFTY99DEC25000CE",
        "local_quantity": 0,
        "broker_quantity": 65,
    }]
    assert latched == [True]


def test_position_reconciliation_ignores_non_nifty_and_flat_rows(monkeypatch):
    monkeypatch.setattr(execution_spine, "list_orders", lambda limit=500: [])
    monkeypatch.setattr(execution_spine.store, "set_kill_switch", lambda *args: (_ for _ in ()).throw(AssertionError("must not latch")))
    monkeypatch.setattr(execution_spine, "record_event", lambda *args: None)
    rows = [
        _broker_position(10, tradingsymbol="BANKNIFTY99DEC50000CE"),
        _broker_position(0),
        _broker_position(5, exchange="NSE", tradingsymbol="NIFTY 50"),
    ]

    result = execution_spine.reconcile_positions_once(broker=PositionBroker(rows))

    assert result["matched"] is True
    assert result["broker"] == {}
