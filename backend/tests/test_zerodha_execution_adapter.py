"""
Coverage gap fill: app/zerodha_execution_adapter.py had no tests despite being
the safety gate between the paper-trading system and any real broker call
(BUY-only, NIFTY-CE/PE-only, and ambiguous-broker-state detection used by
execution_spine's reconciliation path). Uses only a tiny fake Kite client,
no network, no real credentials.
"""
from __future__ import annotations

import pytest

from app.zerodha_execution_adapter import (
    AmbiguousBrokerState,
    ZerodhaExecutionAdapter,
)


class FakeKite:
    def __init__(self, existing_orders=None, order_id="OID-1"):
        self._orders = existing_orders or []
        self._order_id = order_id
        self.last_place_order_kwargs = None

    def place_order(self, **kwargs):
        self.last_place_order_kwargs = kwargs
        return self._order_id

    def orders(self):
        return self._orders

    def trades(self):
        return [{"trade_id": "T1"}]

    def positions(self):
        return {"net": []}


class FakeDataSource:
    def __init__(self, kite):
        self._kite = kite


def _order(**overrides):
    base = {
        "transaction_type": "BUY",
        "tradingsymbol": "NFO:NIFTY25000CE",
        "quantity": 75,
    }
    base.update(overrides)
    return base


def test_constructor_requires_authenticated_data_source():
    class NoKite:
        pass

    with pytest.raises(RuntimeError, match="authenticated ZerodhaDataSource"):
        ZerodhaExecutionAdapter(NoKite())


def test_rejects_sell_orders():
    adapter = ZerodhaExecutionAdapter(FakeDataSource(FakeKite()))
    with pytest.raises(ValueError, match="BUY only"):
        adapter.place_buy_once(_order(transaction_type="SELL"), "tag-1")


def test_rejects_non_nifty_symbol():
    adapter = ZerodhaExecutionAdapter(FakeDataSource(FakeKite()))
    with pytest.raises(ValueError, match="NIFTY CE/PE only"):
        adapter.place_buy_once(_order(tradingsymbol="BANKNIFTY25000CE"), "tag-1")


def test_rejects_non_option_nifty_symbol():
    adapter = ZerodhaExecutionAdapter(FakeDataSource(FakeKite()))
    with pytest.raises(ValueError, match="NIFTY CE/PE only"):
        adapter.place_buy_once(_order(tradingsymbol="NIFTY25000FUT"), "tag-1")


def test_place_buy_once_happy_path_strips_exchange_prefix_and_tags_order():
    kite = FakeKite(order_id="OID-42")
    adapter = ZerodhaExecutionAdapter(FakeDataSource(kite))
    order_id = adapter.place_buy_once(_order(), "vst-tag-77")
    assert order_id == "OID-42"
    assert kite.last_place_order_kwargs["tradingsymbol"] == "NIFTY25000CE"
    assert kite.last_place_order_kwargs["transaction_type"] == "BUY"
    assert kite.last_place_order_kwargs["exchange"] == "NFO"
    assert kite.last_place_order_kwargs["quantity"] == 75
    assert kite.last_place_order_kwargs["tag"] == "vst-tag-77"


def test_list_orders_and_trades_handle_falsy_broker_response():
    class NoneKite(FakeKite):
        def orders(self):
            return None

        def trades(self):
            return None

        def positions(self):
            return None

    adapter = ZerodhaExecutionAdapter(FakeDataSource(NoneKite()))
    assert adapter.list_orders() == []
    assert adapter.list_trades() == []
    assert adapter.positions() == {}


def test_find_order_by_tag_returns_none_when_no_match():
    kite = FakeKite(existing_orders=[
        {"tag": "other-tag", "tradingsymbol": "NIFTY25000CE", "transaction_type": "BUY", "quantity": 75},
    ])
    adapter = ZerodhaExecutionAdapter(FakeDataSource(kite))
    assert adapter.find_order_by_tag(broker_tag="vst-tag-77", order=_order()) is None


def test_find_order_by_tag_returns_single_match():
    matching = {"tag": "vst-tag-77", "tradingsymbol": "NFO:NIFTY25000CE",
                "transaction_type": "BUY", "quantity": 75, "order_id": "OID-1"}
    kite = FakeKite(existing_orders=[
        {"tag": "other-tag", "tradingsymbol": "NIFTY25000CE", "transaction_type": "BUY", "quantity": 75},
        matching,
    ])
    adapter = ZerodhaExecutionAdapter(FakeDataSource(kite))
    result = adapter.find_order_by_tag(broker_tag="vst-tag-77", order=_order())
    assert result == matching


def test_find_order_by_tag_raises_on_ambiguous_duplicates():
    dup1 = {"tag": "vst-tag-77", "tradingsymbol": "NIFTY25000CE", "transaction_type": "BUY", "quantity": 75, "order_id": "A"}
    dup2 = {"tag": "vst-tag-77", "tradingsymbol": "NIFTY25000CE", "transaction_type": "BUY", "quantity": 75, "order_id": "B"}
    kite = FakeKite(existing_orders=[dup1, dup2])
    adapter = ZerodhaExecutionAdapter(FakeDataSource(kite))
    with pytest.raises(AmbiguousBrokerState, match="2 economic orders"):
        adapter.find_order_by_tag(broker_tag="vst-tag-77", order=_order())
