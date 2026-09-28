"""Durable execution ledger for VSTradingAI V7.3.

The ledger intentionally lives in the existing SQLite WAL database so the
single-node Lightsail deployment gets restart-safe idempotency and reconciliation
without introducing a distributed queue before it is operationally necessary.

The API is deliberately persistence-only. It does not talk to a broker and it
does not make trading decisions.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable

from app import store


SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_previews (
    preview_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL,
    order_json TEXT NOT NULL,
    checks_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_execution_previews_idem
    ON execution_previews(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_execution_previews_status
    ON execution_previews(status, created_at DESC);

CREATE TABLE IF NOT EXISTS execution_orders (
    execution_id TEXT PRIMARY KEY,
    preview_id TEXT NOT NULL,
    signal_id TEXT NOT NULL UNIQUE,
    idempotency_key TEXT NOT NULL UNIQUE,
    broker_tag TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    submitted_to_broker INTEGER NOT NULL DEFAULT 0,
    broker_order_id TEXT,
    filled_quantity INTEGER NOT NULL DEFAULT 0,
    average_price REAL,
    last_error TEXT,
    order_json TEXT NOT NULL,
    risk_snapshot_json TEXT,
    quality_snapshot_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submitted_at TEXT,
    reconciled_at TEXT,
    FOREIGN KEY(preview_id) REFERENCES execution_previews(preview_id)
);
CREATE INDEX IF NOT EXISTS idx_execution_orders_status
    ON execution_orders(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_orders_broker_order
    ON execution_orders(broker_order_id);

CREATE TABLE IF NOT EXISTS execution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    detail_json TEXT,
    FOREIGN KEY(execution_id) REFERENCES execution_orders(execution_id)
);
CREATE INDEX IF NOT EXISTS idx_execution_events_execution
    ON execution_events(execution_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_execution_events_type
    ON execution_events(event_type, id DESC);
"""


@contextmanager
def _conn():
    conn = sqlite3.connect(store.DB_PATH, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, default=str, separators=(",", ":"), sort_keys=True)


def _decode_preview(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    item["order"] = json.loads(item.pop("order_json"))
    item["checks"] = json.loads(item.pop("checks_json"))
    return item


def _decode_order(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    item["submitted_to_broker"] = bool(item["submitted_to_broker"])
    item["order"] = json.loads(item.pop("order_json"))
    item["risk_snapshot"] = json.loads(item.pop("risk_snapshot_json")) if item.get("risk_snapshot_json") else None
    item["quality_snapshot"] = json.loads(item.pop("quality_snapshot_json")) if item.get("quality_snapshot_json") else None
    return item


def save_preview(record: dict[str, Any]) -> dict[str, Any]:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO execution_previews
               (preview_id, idempotency_key, signal_id, created_at, expires_at, status, order_json, checks_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record["preview_id"], record["idempotency_key"], record["signal_id"],
                record["created_at"], record["expires_at"], record["status"],
                _json(record["order"]), _json(record["checks"]),
            ),
        )
    return get_preview(record["preview_id"]) or record


def get_preview(preview_id: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM execution_previews WHERE preview_id = ?", (preview_id,)
        ).fetchone()
    return _decode_preview(row)


def set_preview_status(preview_id: str, status: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE execution_previews SET status = ? WHERE preview_id = ?",
            (status, preview_id),
        )


def find_order_by_idempotency_key(idempotency_key: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM execution_orders WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
    return _decode_order(row)


def create_order(record: dict[str, Any]) -> dict[str, Any]:
    now = record.get("created_at") or _now()
    try:
        with _conn() as conn:
            conn.execute(
                """INSERT INTO execution_orders
                   (execution_id, preview_id, signal_id, idempotency_key, broker_tag, status,
                    submitted_to_broker, broker_order_id, filled_quantity, average_price,
                    last_error, order_json, risk_snapshot_json, quality_snapshot_json,
                    created_at, updated_at, submitted_at, reconciled_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record["execution_id"], record["preview_id"], record["signal_id"],
                    record["idempotency_key"], record["broker_tag"], record["status"],
                    1 if record.get("submitted_to_broker") else 0,
                    record.get("broker_order_id"), int(record.get("filled_quantity") or 0),
                    record.get("average_price"), record.get("last_error"), _json(record["order"]),
                    _json(record["risk_snapshot"]) if record.get("risk_snapshot") is not None else None,
                    _json(record["quality_snapshot"]) if record.get("quality_snapshot") is not None else None,
                    now, record.get("updated_at") or now, record.get("submitted_at"),
                    record.get("reconciled_at"),
                ),
            )
    except sqlite3.IntegrityError as exc:
        existing = find_order_by_idempotency_key(record["idempotency_key"])
        if existing is not None:
            record_event(existing["execution_id"], "DUPLICATE_BLOCKED", {
                "idempotency_key": record["idempotency_key"], "reason": str(exc)
            })
        raise ValueError("Duplicate order blocked by durable idempotency key") from exc
    record_event(record["execution_id"], "ORDER_CREATED", {"status": record["status"]})
    return get_order(record["execution_id"]) or record


def get_order(execution_id: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM execution_orders WHERE execution_id = ?", (execution_id,)
        ).fetchone()
    return _decode_order(row)


def list_orders(limit: int = 100) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM execution_orders ORDER BY created_at DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [_decode_order(row) for row in rows if row is not None]


def list_orders_by_status(statuses: Iterable[str], limit: int = 100) -> list[dict[str, Any]]:
    values = tuple(dict.fromkeys(str(s) for s in statuses))
    if not values:
        return []
    placeholders = ",".join("?" for _ in values)
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM execution_orders WHERE status IN ({placeholders}) "
            "ORDER BY updated_at ASC LIMIT ?",
            (*values, max(1, min(int(limit), 500))),
        ).fetchall()
    return [_decode_order(row) for row in rows if row is not None]


def transition_order(
    execution_id: str,
    status: str,
    *,
    submitted_to_broker: bool | None = None,
    broker_order_id: str | None = None,
    filled_quantity: int | None = None,
    average_price: float | None = None,
    last_error: str | None = None,
    risk_snapshot: dict[str, Any] | None = None,
    quality_snapshot: dict[str, Any] | None = None,
    submitted_at: str | None = None,
    reconciled_at: str | None = None,
    event_type: str = "ORDER_STATE_CHANGED",
    event_detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = get_order(execution_id)
    if current is None:
        raise KeyError("Execution order not found")
    updates: list[str] = ["status = ?", "updated_at = ?"]
    values: list[Any] = [status, _now()]
    optional = {
        "submitted_to_broker": (1 if submitted_to_broker else 0) if submitted_to_broker is not None else None,
        "broker_order_id": broker_order_id,
        "filled_quantity": filled_quantity,
        "average_price": average_price,
        "last_error": last_error,
        "risk_snapshot_json": _json(risk_snapshot) if risk_snapshot is not None else None,
        "quality_snapshot_json": _json(quality_snapshot) if quality_snapshot is not None else None,
        "submitted_at": submitted_at,
        "reconciled_at": reconciled_at,
    }
    for column, value in optional.items():
        if value is not None:
            updates.append(f"{column} = ?")
            values.append(value)
    values.append(execution_id)
    with _conn() as conn:
        conn.execute(
            f"UPDATE execution_orders SET {', '.join(updates)} WHERE execution_id = ?",
            values,
        )
    record_event(
        execution_id,
        event_type,
        event_detail or {"from": current["status"], "to": status},
    )
    updated = get_order(execution_id)
    if updated is None:
        raise KeyError("Execution order disappeared after update")
    return updated


def record_event(execution_id: str | None, event_type: str, detail: dict[str, Any] | None = None) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO execution_events (execution_id, event_type, created_at, detail_json) VALUES (?, ?, ?, ?)",
            (execution_id, event_type, _now(), _json(detail or {})),
        )


def list_events(execution_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    with _conn() as conn:
        if execution_id:
            rows = conn.execute(
                "SELECT * FROM execution_events WHERE execution_id = ? ORDER BY id DESC LIMIT ?",
                (execution_id, max(1, min(int(limit), 1000))),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM execution_events ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit), 1000)),),
            ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["detail"] = json.loads(item.pop("detail_json") or "{}")
        result.append(item)
    return result


def event_count(event_type: str) -> int:
    with _conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM execution_events WHERE event_type = ?", (event_type,)
        ).fetchone()
    return int(row["n"] if row else 0)


def status_counts() -> dict[str, int]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM execution_orders GROUP BY status"
        ).fetchall()
    return {str(row["status"]): int(row["n"]) for row in rows}


def blocking_exposure(exclude_execution_id: str | None = None) -> list[dict[str, Any]]:
    blocking = ("SUBMITTING", "ACKNOWLEDGED", "OPEN", "PARTIAL", "UNKNOWN")
    items = list_orders_by_status(blocking, limit=200)
    if exclude_execution_id:
        items = [item for item in items if item["execution_id"] != exclude_execution_id]
    return items
