from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass
class PreviewRecord:
    preview_id: str
    idempotency_key: str
    created_at: str
    expires_at: str
    status: str
    order: dict[str, Any]
    checks: list[dict[str, Any]]


_previews: dict[str, PreviewRecord] = {}
_orders: list[dict[str, Any]] = []
_lock = Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _key(order: dict[str, Any]) -> str:
    canonical = json.dumps(order, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


def create_preview(order: dict[str, Any], capital: float, max_utilization_pct: float, lot_size: int) -> dict[str, Any]:
    qty = int(order["quantity"])
    price = float(order.get("price") or order.get("estimated_price") or 0)
    checks = [
        {"name": "quantity_positive", "passed": qty > 0, "detail": f"quantity={qty}"},
        {"name": "lot_multiple", "passed": qty % lot_size == 0, "detail": f"lot_size={lot_size}"},
        {"name": "price_positive", "passed": price > 0, "detail": f"price={price}"},
    ]
    notional = qty * price
    max_notional = capital * max_utilization_pct / 100
    checks.append({"name": "capital_utilization", "passed": notional <= max_notional,
                   "detail": f"notional={notional:.2f}, allowed={max_notional:.2f}"})
    approved = all(c["passed"] for c in checks)
    idem = order.get("idempotency_key") or _key(order)
    preview_id = hashlib.sha256(f"{idem}:{_now().isoformat()}".encode()).hexdigest()[:20]
    created = _now()
    record = PreviewRecord(
        preview_id=preview_id,
        idempotency_key=idem,
        created_at=created.isoformat(),
        expires_at=created.replace(microsecond=0).isoformat(),
        status="READY" if approved else "BLOCKED",
        order={**order, "estimated_notional": round(notional, 2)},
        checks=checks,
    )
    with _lock:
        _previews[preview_id] = record
    return {**asdict(record), "approved": approved, "execution_mode": "MANUAL_CONFIRMATION_ONLY"}


def confirm(preview_id: str, confirmation_text: str, live_enabled: bool) -> dict[str, Any]:
    if confirmation_text != "CONFIRM":
        raise ValueError("confirmation_text must be exactly CONFIRM")
    with _lock:
        record = _previews.get(preview_id)
        if not record:
            raise KeyError("Preview not found")
        if record.status != "READY":
            raise ValueError("Preview is not ready")
        if any(o["idempotency_key"] == record.idempotency_key for o in _orders):
            raise ValueError("Duplicate order blocked by idempotency key")
        order = {
            "order_id": f"MANUAL-{len(_orders)+1:06d}",
            "preview_id": preview_id,
            "idempotency_key": record.idempotency_key,
            "status": "AWAITING_BROKER_SUBMISSION" if live_enabled else "SIMULATED_CONFIRMED",
            "submitted_to_broker": False,
            "created_at": _now().isoformat(),
            "order": record.order,
        }
        _orders.append(order)
        record.status = "CONFIRMED"
    return order


def list_orders() -> list[dict[str, Any]]:
    with _lock:
        return list(reversed(_orders[-100:]))
