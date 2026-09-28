"""Narrow Zerodha execution adapter with reconciliation-first semantics.

This adapter deliberately does not implement automatic retries for order POSTs.
A transport error after submission is ambiguous and must be handled as UNKNOWN
by execution_spine.py, then reconciled against broker truth.
"""
from __future__ import annotations

from typing import Any


class AmbiguousBrokerState(RuntimeError):
    pass


class ZerodhaExecutionAdapter:
    def __init__(self, data_source: Any):
        kite = getattr(data_source, "_kite", None)
        if kite is None:
            raise RuntimeError("Zerodha execution adapter requires an authenticated ZerodhaDataSource")
        self._kite = kite

    @staticmethod
    def _validate(order: dict[str, Any]) -> None:
        side = str(order.get("transaction_type") or "").upper()
        symbol = str(order.get("tradingsymbol") or "").upper().replace("NFO:", "")
        if side != "BUY":
            raise ValueError("VST live entry adapter permits BUY only")
        if not (symbol.startswith("NIFTY") and symbol.endswith(("CE", "PE"))):
            raise ValueError("VST live entry adapter permits NIFTY CE/PE only")

    def place_buy_once(self, order: dict[str, Any], broker_tag: str) -> str:
        self._validate(order)
        symbol = str(order["tradingsymbol"]).upper().replace("NFO:", "")
        # No retry wrapper here. If this call raises after the broker accepted it,
        # the caller MUST mark the execution UNKNOWN and reconcile by broker_tag.
        return str(self._kite.place_order(
            variety="regular",
            exchange="NFO",
            tradingsymbol=symbol,
            transaction_type="BUY",
            quantity=int(order["quantity"]),
            product=str(order.get("product") or "MIS"),
            order_type=str(order.get("order_type") or "MARKET"),
            price=order.get("price"),
            tag=broker_tag,
        ))

    def list_orders(self) -> list[dict[str, Any]]:
        return list(self._kite.orders() or [])

    def list_trades(self) -> list[dict[str, Any]]:
        return list(self._kite.trades() or [])

    def positions(self) -> dict[str, Any]:
        return dict(self._kite.positions() or {})

    def find_order_by_tag(self, *, broker_tag: str, order: dict[str, Any]) -> dict[str, Any] | None:
        symbol = str(order.get("tradingsymbol") or "").upper().replace("NFO:", "")
        side = str(order.get("transaction_type") or "BUY").upper()
        qty = int(order.get("quantity") or 0)
        matches = []
        for item in self.list_orders():
            tag = str(item.get("tag") or "")
            item_symbol = str(item.get("tradingsymbol") or "").upper().replace("NFO:", "")
            item_side = str(item.get("transaction_type") or "").upper()
            item_qty = int(item.get("quantity") or 0)
            if tag == broker_tag and item_symbol == symbol and item_side == side and item_qty == qty:
                matches.append(item)
        if len(matches) > 1:
            raise AmbiguousBrokerState(
                f"Broker returned {len(matches)} economic orders for correlation tag {broker_tag}"
            )
        return matches[0] if matches else None
