"""Controlled live execution spine for VSTradingAI.

This module is deterministic infrastructure, not a strategy. It only accepts a
human-confirmed execution created by execution_readiness.py and never gives an
AI agent direct broker-write capability.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app import store
from app.config import settings
from app.data_quality_gate import current_live_data_quality, evaluate_order_quote
from app.execution_ledger import (
    blocking_exposure,
    event_count,
    get_order,
    list_events,
    list_orders,
    list_orders_by_status,
    record_event,
    status_counts,
    transition_order,
)
from app.risk_supervisor import status as risk_status
from app.position_protection import validate_protection_plan
from app.zerodha_execution_adapter import AmbiguousBrokerState


MAX_SPREAD_PCT = max(0.1, float(settings.execution_max_spread_pct))
BROKER_STATUS_MAP = {
    "COMPLETE": "COMPLETE",
    "REJECTED": "REJECTED",
    "CANCELLED": "CANCELLED",
    "OPEN": "OPEN",
    "TRIGGER PENDING": "OPEN",
    "VALIDATION PENDING": "ACKNOWLEDGED",
    "PUT ORDER REQ RECEIVED": "ACKNOWLEDGED",
    "MODIFY VALIDATION PENDING": "ACKNOWLEDGED",
    "MODIFY PENDING": "ACKNOWLEDGED",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def entry_window_status(now: datetime | None = None) -> dict[str, Any]:
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Asia/Kolkata"))
    hh, mm = (int(value) for value in settings.execution_entry_cutoff_time.split(":", 1))
    cutoff = datetime.combine(local.date(), time(hh, mm), tzinfo=local.tzinfo)
    approved = local < cutoff
    return {"approved": approved, "local_time": local.isoformat(), "cutoff": cutoff.isoformat(), "blocker": None if approved else "ENTRY_CUTOFF_REACHED"}


def _setup_gate(order_record: dict[str, Any]) -> dict[str, Any]:
    order = order_record["order"]
    setup_id = order.get("setup_id")
    if not setup_id:
        raise ValueError("Execution is not linked to an approved setup_id")
    setup = store.get_trade_setup(int(setup_id))
    if setup is None:
        raise ValueError("Trade setup not found")
    if setup.get("status") != "APPROVED" or setup.get("grade") not in {"A", "A+"}:
        raise ValueError("DecisionGate requires an APPROVED A/A+ setup")
    if str(order.get("transaction_type") or "").upper() != "BUY":
        raise ValueError("VST entry execution is BUY only")
    symbol = str(order.get("tradingsymbol") or "").upper().replace("NFO:", "")
    if not (symbol.startswith("NIFTY") and symbol.endswith(("CE", "PE"))):
        raise ValueError("VST entry execution is restricted to NIFTY CE/PE")
    protection = validate_protection_plan(setup, order)
    if not protection["approved"]:
        raise ValueError("PositionProtectionGate blocked: " + ",".join(protection["blockers"]))
    return setup


def execution_gate_status(exclude_execution_id: str | None = None) -> dict[str, Any]:
    risk = risk_status()
    blockers: list[str] = []
    exposure = blocking_exposure(exclude_execution_id=exclude_execution_id)
    if risk.get("blocked"):
        blockers.append("RISK_GATE_BLOCKED")
    if store.get_open_position() or store.get_open_paper_trade():
        blockers.append("POSITION_ALREADY_OPEN")
    if exposure:
        blockers.append("UNRESOLVED_EXECUTION_EXPOSURE")
    return {
        "approved": not blockers,
        "blockers": blockers,
        "risk": risk,
        "blocking_executions": [
            {"execution_id": item["execution_id"], "status": item["status"], "broker_tag": item["broker_tag"]}
            for item in exposure
        ],
    }


def submit_once(
    execution_id: str,
    *,
    broker: Any,
    data_source: Any,
    live_enabled: bool,
    confirmation_text: str,
) -> dict[str, Any]:
    if not live_enabled:
        raise ValueError("Live broker orders are disabled by configuration")
    if confirmation_text != "EXECUTE LIVE":
        raise ValueError("confirmation_text must be exactly EXECUTE LIVE")
    record = get_order(execution_id)
    if record is None:
        raise KeyError("Execution order not found")
    if record["status"] == "UNKNOWN":
        raise ValueError("UNKNOWN order must be reconciled; blind retry is forbidden")
    if record["status"] != "AWAITING_BROKER_SUBMISSION":
        raise ValueError(f"Execution is not submit-ready: {record['status']}")

    setup = _setup_gate(record)
    entry_window = entry_window_status()
    if not entry_window["approved"]:
        raise ValueError(str(entry_window["blocker"]))
    gate = execution_gate_status(exclude_execution_id=execution_id)
    if not gate["approved"]:
        raise ValueError("Execution gate blocked: " + ",".join(gate["blockers"]))

    quality = current_live_data_quality()
    if not quality.approved:
        raise ValueError("DataQualityGate blocked: " + ",".join(quality.blockers))
    option_snapshot = data_source.get_option_chain(atm_range=20)
    quote_quality = evaluate_order_quote(record["order"], option_snapshot, max_spread_pct=MAX_SPREAD_PCT)
    if not quote_quality.approved:
        raise ValueError("Order market-quality gate blocked: " + ",".join(quote_quality.blockers))
    quality_snapshot = {
        "runtime": quality.to_dict(),
        "order_quote": quote_quality.to_dict(),
        "setup_id": setup.get("id"),
        "grade": setup.get("grade"),
    }

    # Persist SUBMITTING before touching the broker. If the process dies after
    # this write, startup/reconciliation sees a non-terminal economic intent.
    transition_order(
        execution_id,
        "SUBMITTING",
        risk_snapshot=gate["risk"],
        quality_snapshot=quality_snapshot,
        event_type="BROKER_SUBMISSION_STARTED",
        event_detail={"broker_tag": record["broker_tag"]},
    )
    try:
        broker_order_id = broker.place_buy_once(record["order"], record["broker_tag"])
    except Exception as exc:
        # Critical rule: no automatic retry. Broker may have accepted the POST.
        return transition_order(
            execution_id,
            "UNKNOWN",
            submitted_to_broker=True,
            last_error=str(exc)[:500],
            submitted_at=_now(),
            event_type="BROKER_SUBMISSION_AMBIGUOUS",
            event_detail={"error": str(exc)[:500], "retry_allowed": False},
        )
    return transition_order(
        execution_id,
        "ACKNOWLEDGED",
        submitted_to_broker=True,
        broker_order_id=str(broker_order_id),
        last_error="",
        submitted_at=_now(),
        event_type="BROKER_ACKNOWLEDGED",
        event_detail={"broker_order_id": str(broker_order_id)},
    )


def reconcile_once(execution_id: str, *, broker: Any) -> dict[str, Any]:
    record = get_order(execution_id)
    if record is None:
        raise KeyError("Execution order not found")
    if record["status"] in {"SIMULATED_CONFIRMED", "AWAITING_BROKER_SUBMISSION"}:
        raise ValueError(f"Execution has not been submitted: {record['status']}")
    try:
        broker_order = broker.find_order_by_tag(
            broker_tag=record["broker_tag"], order=record["order"]
        )
    except AmbiguousBrokerState as exc:
        store.set_kill_switch(True, f"Duplicate/ambiguous broker state for {execution_id}: {exc}")
        return transition_order(
            execution_id,
            "UNKNOWN",
            last_error=str(exc)[:500],
            reconciled_at=_now(),
            event_type="RECONCILIATION_AMBIGUOUS",
            event_detail={"error": str(exc)[:500], "kill_switch_latched": True},
        )
    except Exception as exc:
        return transition_order(
            execution_id,
            "UNKNOWN",
            last_error=f"reconciliation failed: {exc}"[:500],
            reconciled_at=_now(),
            event_type="RECONCILIATION_FAILED",
            event_detail={"error": str(exc)[:500]},
        )

    if broker_order is None:
        # Absence in one broker snapshot is not sufficient proof that the POST
        # was never accepted. Keep UNKNOWN and require a later/manual resolution.
        return transition_order(
            execution_id,
            "UNKNOWN",
            last_error="No matching broker order found yet; resubmission remains blocked",
            reconciled_at=_now(),
            event_type="RECONCILIATION_NOT_FOUND",
            event_detail={"retry_allowed": False},
        )

    broker_status = str(broker_order.get("status") or "").upper()
    state = BROKER_STATUS_MAP.get(broker_status, "ACKNOWLEDGED")
    filled = int(broker_order.get("filled_quantity") or 0)
    quantity = int(broker_order.get("quantity") or record["order"].get("quantity") or 0)
    if state == "OPEN" and 0 < filled < quantity:
        state = "PARTIAL"
    return transition_order(
        execution_id,
        state,
        submitted_to_broker=True,
        broker_order_id=str(broker_order.get("order_id") or record.get("broker_order_id") or "") or None,
        filled_quantity=filled,
        average_price=float(broker_order.get("average_price") or 0) or None,
        last_error=str(broker_order.get("status_message") or "")[:500],
        reconciled_at=_now(),
        event_type="RECONCILED_WITH_BROKER",
        event_detail={"broker_status": broker_status, "resolved_state": state},
    )


def reconcile_unknowns(*, broker: Any, limit: int = 50) -> list[dict[str, Any]]:
    items = list_orders_by_status(("UNKNOWN", "SUBMITTING", "ACKNOWLEDGED", "OPEN", "PARTIAL"), limit=limit)
    return [reconcile_once(item["execution_id"], broker=broker) for item in items]


def reconcile_positions_once(*, broker: Any) -> dict[str, Any]:
    """Compare today's locally recorded fills with current NFO broker positions.

    This check is read-only at the broker. Any mismatch latches the persistent
    kill switch and therefore blocks new entries until a human investigates.
    """
    trading_day = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    local: dict[str, int] = {}
    for item in list_orders(limit=500):
        created_at = datetime.fromisoformat(str(item["created_at"]).replace("Z", "+00:00"))
        if created_at.astimezone(ZoneInfo("Asia/Kolkata")).date() != trading_day:
            continue
        if item["status"] not in {"PARTIAL", "COMPLETE"}:
            continue
        symbol = str(item["order"].get("tradingsymbol") or "").upper().replace("NFO:", "")
        filled = int(item.get("filled_quantity") or 0)
        if symbol and filled:
            local[symbol] = local.get(symbol, 0) + filled

    broker_snapshot = broker.positions()
    broker_net: dict[str, int] = {}
    for item in (broker_snapshot or {}).get("net", []) or []:
        exchange = str(item.get("exchange") or "").upper()
        symbol = str(item.get("tradingsymbol") or "").upper().replace("NFO:", "")
        quantity = int(item.get("quantity") or 0)
        if exchange == "NFO" and symbol.startswith("NIFTY") and symbol.endswith(("CE", "PE")) and quantity:
            broker_net[symbol] = broker_net.get(symbol, 0) + quantity

    symbols = sorted(set(local) | set(broker_net))
    mismatches = [
        {"tradingsymbol": symbol, "local_quantity": local.get(symbol, 0), "broker_quantity": broker_net.get(symbol, 0)}
        for symbol in symbols
        if local.get(symbol, 0) != broker_net.get(symbol, 0)
    ]
    matched = not mismatches
    detail = {"trading_day": trading_day.isoformat(), "matched": matched, "local": local, "broker": broker_net, "mismatches": mismatches}
    if not matched:
        store.set_kill_switch(True, "Broker/local NIFTY position mismatch")
        record_event(None, "POSITION_RECONCILIATION_MISMATCH", {**detail, "kill_switch_latched": True})
    else:
        record_event(None, "POSITION_RECONCILIATION_MATCHED", detail)
    return detail


def status_snapshot() -> dict[str, Any]:
    counts = status_counts()
    unknown = counts.get("UNKNOWN", 0)
    gate = execution_gate_status()
    return {
        "ready": gate["approved"] and unknown == 0,
        "order_state_counts": counts,
        "unknown_orders": unknown,
        "duplicate_attempts_blocked": event_count("DUPLICATE_BLOCKED"),
        "reconciliation_failures": event_count("RECONCILIATION_FAILED") + event_count("RECONCILIATION_AMBIGUOUS"),
        "execution_gate": gate,
        "rules": {
            "options_buy_only": True,
            "grades": ["A", "A+"],
            "human_confirmation": True,
            "blind_broker_retry": False,
            "unknown_blocks_new_entries": True,
        },
    }


def prometheus_text() -> str:
    snapshot = status_snapshot()
    risk = snapshot["execution_gate"]["risk"]
    lines = [
        "# HELP vst_order_unknown_current Unresolved broker order states.",
        "# TYPE vst_order_unknown_current gauge",
        f"vst_order_unknown_current {snapshot['unknown_orders']}",
        "# HELP vst_duplicate_order_prevented_total Durable duplicate execution attempts prevented.",
        "# TYPE vst_duplicate_order_prevented_total counter",
        f"vst_duplicate_order_prevented_total {snapshot['duplicate_attempts_blocked']}",
        "# HELP vst_kill_switch_state Persistent emergency kill switch state.",
        "# TYPE vst_kill_switch_state gauge",
        f"vst_kill_switch_state {1 if risk.get('kill_switch') else 0}",
        "# HELP vst_daily_pnl_rupees Current trading-day PnL used by RiskGate.",
        "# TYPE vst_daily_pnl_rupees gauge",
        f"vst_daily_pnl_rupees {float(risk.get('daily_pnl') or 0.0)}",
        "# HELP vst_trades_today Current trading-day trade count.",
        "# TYPE vst_trades_today gauge",
        f"vst_trades_today {int(risk.get('trades_today') or 0)}",
    ]
    for state, count in sorted(snapshot["order_state_counts"].items()):
        lines.append(f'vst_execution_orders{{status="{state}"}} {count}')
    try:
        quality = current_live_data_quality()
        market_age = next((c for c in quality.checks if c["name"] == "market_snapshot_fresh"), None)
        # The detailed age remains available through the JSON status endpoint;
        # this metric focuses on gate state to avoid parsing detail strings.
        lines.extend([
            "# HELP vst_data_quality_gate_state 1 when deterministic market-data quality gate is green.",
            "# TYPE vst_data_quality_gate_state gauge",
            f"vst_data_quality_gate_state {1 if quality.approved else 0}",
        ])
    except Exception:
        lines.extend([
            "# HELP vst_data_quality_gate_state 1 when deterministic market-data quality gate is green.",
            "# TYPE vst_data_quality_gate_state gauge",
            "vst_data_quality_gate_state 0",
        ])
    return "\n".join(lines) + "\n"


def recent_events(execution_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return list_events(execution_id=execution_id, limit=limit)
