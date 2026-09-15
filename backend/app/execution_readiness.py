from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app import store
from app.config import settings
from app.execution_ledger import (
    create_order,
    find_order_by_idempotency_key,
    get_preview,
    list_orders as ledger_list_orders,
    record_event,
    save_preview,
    set_preview_status,
)
from app.risk_supervisor import status as risk_status


PREVIEW_TTL_SEC = max(30, int(settings.execution_preview_ttl_sec))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _key(order: dict[str, Any]) -> str:
    canonical = json.dumps(order, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


def _signal_id(order: dict[str, Any], idem: str) -> str:
    supplied = str(order.get("signal_id") or "").strip()
    if supplied:
        return supplied[:64]
    return "SIG-" + hashlib.sha256(idem.encode()).hexdigest()[:20]


def _broker_tag(idem: str) -> str:
    # Kite tags are correlation identifiers, NOT broker-side idempotency keys.
    # Keep compact and deterministic so an UNKNOWN submission can be reconciled.
    return "vst" + hashlib.sha256(idem.encode()).hexdigest()[:17]


def _is_nifty_option_symbol(symbol: str) -> bool:
    symbol = symbol.upper().replace("NFO:", "")
    return symbol.startswith("NIFTY") and symbol.endswith(("CE", "PE"))


def _validate_order(order: dict[str, Any], capital: float, max_utilization_pct: float, lot_size: int) -> tuple[list[dict[str, Any]], float]:
    qty = int(order["quantity"])
    price = float(order.get("price") or order.get("estimated_price") or 0)
    symbol = str(order.get("tradingsymbol") or "").upper()
    side = str(order.get("transaction_type") or "").upper()
    checks = [
        {"name": "quantity_positive", "passed": qty > 0, "detail": f"quantity={qty}"},
        {"name": "lot_multiple", "passed": lot_size > 0 and qty % lot_size == 0, "detail": f"lot_size={lot_size}"},
        {"name": "price_positive", "passed": price > 0, "detail": f"price={price}"},
        {"name": "buy_to_open_only", "passed": side == "BUY", "detail": f"transaction_type={side or 'missing'}"},
        {"name": "nifty_option_only", "passed": _is_nifty_option_symbol(symbol), "detail": f"tradingsymbol={symbol or 'missing'}"},
    ]
    notional = qty * price
    max_notional = capital * max_utilization_pct / 100
    checks.append({
        "name": "capital_utilization",
        "passed": notional <= max_notional,
        "detail": f"notional={notional:.2f}, allowed={max_notional:.2f}",
    })
    return checks, notional


def create_preview(order: dict[str, Any], capital: float, max_utilization_pct: float, lot_size: int) -> dict[str, Any]:
    checks, notional = _validate_order(order, capital, max_utilization_pct, lot_size)
    approved = all(c["passed"] for c in checks)
    idem = str(order.get("idempotency_key") or _key(order))
    created = _now()
    signal_id = _signal_id(order, idem)
    preview_id = "PRV-" + hashlib.sha256(f"{idem}:{created.isoformat()}".encode()).hexdigest()[:20]
    record = {
        "preview_id": preview_id,
        "idempotency_key": idem,
        "signal_id": signal_id,
        "created_at": created.isoformat(),
        "expires_at": (created + timedelta(seconds=PREVIEW_TTL_SEC)).isoformat(),
        "status": "READY" if approved else "BLOCKED",
        "order": {**order, "signal_id": signal_id, "estimated_notional": round(notional, 2)},
        "checks": checks,
    }
    save_preview(record)
    return {**record, "approved": approved, "execution_mode": "MANUAL_CONFIRMATION_ONLY"}


def _validate_live_confirmation(record: dict[str, Any]) -> dict[str, Any]:
    order = record["order"]
    setup_id = order.get("setup_id")
    if not setup_id:
        raise ValueError("Live execution requires an approved A/A+ setup_id")
    setup = store.get_trade_setup(int(setup_id))
    if setup is None:
        raise ValueError("Trade setup not found")
    if setup.get("status") != "APPROVED":
        raise ValueError("Live execution requires an APPROVED trade setup")
    if setup.get("grade") not in {"A", "A+"}:
        raise ValueError("Only A/A+ setups are eligible for live execution")
    plan_type = str(setup.get("option_type") or "").upper()
    symbol = str(order.get("tradingsymbol") or "").upper()
    if plan_type and not symbol.endswith(plan_type):
        raise ValueError("Order option type does not match the approved setup")
    risk = risk_status()
    if risk.get("blocked"):
        raise ValueError("Independent RiskGate is blocked")
    return {"setup_id": int(setup_id), "grade": setup.get("grade"), "risk": risk}


def confirm(preview_id: str, confirmation_text: str, live_enabled: bool) -> dict[str, Any]:
    if confirmation_text != "CONFIRM":
        raise ValueError("confirmation_text must be exactly CONFIRM")
    record = get_preview(preview_id)
    if not record:
        raise KeyError("Preview not found")
    existing = find_order_by_idempotency_key(record["idempotency_key"])
    if existing is not None:
        record_event(existing["execution_id"], "DUPLICATE_BLOCKED", {
            "idempotency_key": record["idempotency_key"],
            "source": "execution_confirm",
        })
        raise ValueError("Duplicate order blocked by durable idempotency key")
    if record["status"] != "READY":
        raise ValueError("Preview is not ready")
    expires = datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
    if _now() >= expires.astimezone(timezone.utc):
        set_preview_status(preview_id, "EXPIRED")
        raise ValueError("Preview expired; create a fresh preview")
    live_validation = _validate_live_confirmation(record) if live_enabled else None
    idem = record["idempotency_key"]
    execution_id = "EXE-" + hashlib.sha256(f"{preview_id}:{idem}".encode()).hexdigest()[:20]
    order = {
        "execution_id": execution_id,
        # Compatibility alias retained for existing clients that displayed order_id.
        "order_id": execution_id,
        "preview_id": preview_id,
        "signal_id": record["signal_id"],
        "idempotency_key": idem,
        "broker_tag": _broker_tag(idem),
        "status": "AWAITING_BROKER_SUBMISSION" if live_enabled else "SIMULATED_CONFIRMED",
        "submitted_to_broker": False,
        "created_at": _now().isoformat(),
        "order": record["order"],
        "risk_snapshot": live_validation["risk"] if live_validation else None,
        "quality_snapshot": None,
    }
    created = create_order(order)
    set_preview_status(preview_id, "CONFIRMED")
    return created


def list_orders() -> list[dict[str, Any]]:
    return ledger_list_orders(100)
