"""Advanced, restart-safe paper-trade lifecycle management.

Implements paper-only partial profit booking, break-even stop movement and a
percentage trailing stop. State is persisted in SQLite so a service restart
cannot forget the remaining quantity or active stop.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app import store
from app.config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_management(trade: dict[str, Any]) -> dict[str, Any]:
    with store._conn() as conn:
        row = conn.execute("SELECT * FROM paper_trade_management WHERE trade_id=?", (trade["id"],)).fetchone()
        if row:
            return dict(row)
        conn.execute(
            """INSERT INTO paper_trade_management
               (trade_id, original_quantity, remaining_quantity, highest_price,
                active_stop_loss, trail_distance_pct, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                trade["id"], trade["quantity"], trade["quantity"], trade["entry_price"],
                trade["stop_loss"], 10.0, _now(),
            ),
        )
        row = conn.execute("SELECT * FROM paper_trade_management WHERE trade_id=?", (trade["id"],)).fetchone()
        return dict(row)


def get_management(trade_id: int) -> dict[str, Any] | None:
    with store._conn() as conn:
        row = conn.execute("SELECT * FROM paper_trade_management WHERE trade_id=?", (trade_id,)).fetchone()
        return dict(row) if row else None


def get_open_management() -> dict[str, Any] | None:
    trade = store.get_open_paper_trade()
    if not trade:
        return None
    return {"trade": trade, "management": ensure_management(trade)}


def configure(trade_id: int, *, trailing_enabled: bool, trail_distance_pct: float) -> dict[str, Any]:
    if not 2.0 <= trail_distance_pct <= 30.0:
        raise ValueError("trail_distance_pct must be between 2 and 30")
    with store._conn() as conn:
        current = conn.execute("SELECT * FROM paper_trade_management WHERE trade_id=?", (trade_id,)).fetchone()
        if current is None:
            raise ValueError("Paper-trade management state not found")
        conn.execute(
            "UPDATE paper_trade_management SET trailing_enabled=?, trail_distance_pct=?, updated_at=? WHERE trade_id=?",
            (1 if trailing_enabled else 0, trail_distance_pct, _now(), trade_id),
        )
    return get_management(trade_id) or {}


def _partial_quantity(remaining: int) -> int:
    lot = max(1, int(settings.nifty_lot_size))
    if remaining < lot * 2:
        return 0
    half_lots = max(1, (remaining // lot) // 2)
    return min(remaining - lot, half_lots * lot)


def _persist(state: dict[str, Any]) -> dict[str, Any]:
    with store._conn() as conn:
        conn.execute(
            """UPDATE paper_trade_management SET remaining_quantity=?, realized_quantity=?,
               realized_gross_pnl=?, realized_costs=?, highest_price=?, active_stop_loss=?,
               partial_target_done=?, breakeven_armed=?, trailing_enabled=?, trail_distance_pct=?,
               last_action=?, updated_at=? WHERE trade_id=?""",
            (
                state["remaining_quantity"], state["realized_quantity"], state["realized_gross_pnl"],
                state["realized_costs"], state["highest_price"], state["active_stop_loss"],
                state["partial_target_done"], state["breakeven_armed"], state["trailing_enabled"],
                state["trail_distance_pct"], state["last_action"], _now(), state["trade_id"],
            ),
        )
    return get_management(state["trade_id"]) or state


def evaluate(trade: dict[str, Any], current_price: float, *, force_eod: bool = False) -> dict[str, Any]:
    """Evaluate one quote and persist lifecycle state.

    Returns an action without ever calling a broker. Final close accounting
    includes previously realized partial P&L and costs.
    """
    state = ensure_management(trade)
    state["highest_price"] = max(float(state["highest_price"]), current_price)
    actions: list[str] = []

    target_1 = float(trade.get("target_1") or 0)
    target_2 = float(trade.get("target_2") or 0)
    entry = float(trade["entry_price"])

    if target_1 and current_price >= target_1 and not state["partial_target_done"]:
        qty = _partial_quantity(int(state["remaining_quantity"]))
        if qty:
            gross = round((current_price - entry) * qty, 2)
            costs = round((entry + current_price) * qty * settings.paper_cost_rate, 2)
            state["remaining_quantity"] -= qty
            state["realized_quantity"] += qty
            state["realized_gross_pnl"] = round(float(state["realized_gross_pnl"]) + gross, 2)
            state["realized_costs"] = round(float(state["realized_costs"]) + costs, 2)
            actions.append(f"PARTIAL_EXIT_{qty}")
        state["partial_target_done"] = 1
        state["breakeven_armed"] = 1
        state["active_stop_loss"] = max(float(state["active_stop_loss"]), entry)
        actions.append("STOP_TO_BREAKEVEN")

    if state["trailing_enabled"] and state["breakeven_armed"]:
        trail = float(state["highest_price"]) * (1.0 - float(state["trail_distance_pct"]) / 100.0)
        new_stop = max(float(state["active_stop_loss"]), entry, round(trail, 2))
        if new_stop > float(state["active_stop_loss"]):
            state["active_stop_loss"] = new_stop
            actions.append("TRAILING_STOP_RAISED")

    close_reason = close_status = None
    if force_eod:
        close_reason, close_status = "END_OF_DAY", "CLOSED_EOD"
    elif current_price <= float(state["active_stop_loss"]):
        close_reason = "TRAILING_STOP" if state["breakeven_armed"] else "STOP_LOSS"
        close_status = "CLOSED_TRAILING" if state["breakeven_armed"] else "CLOSED_SL"
    elif target_2 and current_price >= target_2:
        close_reason, close_status = "TARGET_2", "CLOSED_TARGET_2"

    if close_status:
        remaining = int(state["remaining_quantity"])
        remaining_gross = round((current_price - entry) * remaining, 2)
        remaining_costs = round((entry + current_price) * remaining * settings.paper_cost_rate, 2)
        gross = round(float(state["realized_gross_pnl"]) + remaining_gross, 2)
        costs = round(float(state["realized_costs"]) + remaining_costs, 2)
        closed = store.close_paper_trade_managed(
            trade["id"], current_price, close_status, costs, close_reason, gross
        )
        state["remaining_quantity"] = 0
        state["realized_quantity"] = int(state["original_quantity"])
        state["last_action"] = close_reason
        _persist(state)
        return {
            "action": "CLOSED", "reason": close_reason, "status": close_status,
            "management": get_management(trade["id"]), **(closed or {}),
        }

    state["last_action"] = "+".join(actions) if actions else "HOLD"
    persisted = _persist(state)
    unrealized = round((current_price - entry) * int(persisted["remaining_quantity"]), 2)
    realized_net = round(float(persisted["realized_gross_pnl"]) - float(persisted["realized_costs"]), 2)
    return {
        "action": "MANAGED" if actions else "HOLD", "actions": actions,
        "trade_id": trade["id"], "current_price": current_price,
        "remaining_quantity": persisted["remaining_quantity"],
        "active_stop_loss": persisted["active_stop_loss"],
        "highest_price": persisted["highest_price"],
        "realized_net_pnl": realized_net, "unrealized_pnl": unrealized,
        "management": persisted,
    }


def close_manually(trade: dict[str, Any], current_price: float, reason: str = "MANUAL") -> dict[str, Any] | None:
    state = ensure_management(trade)
    remaining = int(state["remaining_quantity"])
    entry = float(trade["entry_price"])
    gross = round(float(state["realized_gross_pnl"]) + (current_price - entry) * remaining, 2)
    costs = round(float(state["realized_costs"]) + (entry + current_price) * remaining * settings.paper_cost_rate, 2)
    closed = store.close_paper_trade_managed(trade["id"], current_price, "CLOSED_MANUAL", costs, reason, gross)
    if closed:
        state["remaining_quantity"] = 0
        state["realized_quantity"] = int(state["original_quantity"])
        state["last_action"] = reason
        _persist(state)
    return closed
