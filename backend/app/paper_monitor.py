"""Restart-safe automated paper-trade monitor.

The worker reads the single OPEN paper trade from SQLite on every iteration,
so a backend restart does not lose monitoring state. It only observes Zerodha
or mock quotes and updates the paper ledger; it never calls place_order().
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app import store
from app.config import settings
from app.observability import record_alert

logger = logging.getLogger("vstradingai.paper_monitor")


@dataclass
class MonitorState:
    running: bool = False
    iterations: int = 0
    successful_quotes: int = 0
    quote_failures: int = 0
    last_checked_at: str | None = None
    last_price: float | None = None
    last_action: str = "NOT_STARTED"
    last_error: str | None = None
    active_trade_id: int | None = None


_state = MonitorState()
_lock = threading.RLock()


def _write_notification(event: dict[str, Any]) -> None:
    path = Path(settings.paper_notification_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str, separators=(",", ":")) + "\n")


def _is_eod(now: datetime | None = None) -> bool:
    local_now = now or datetime.now(ZoneInfo(settings.app_timezone))
    hh, mm = [int(x) for x in settings.paper_eod_exit_time.split(":", 1)]
    return (local_now.hour, local_now.minute) >= (hh, mm)


def _option_price(data_source: Any, trade: dict[str, Any]) -> tuple[float, str | None]:
    snapshot = data_source.get_option_chain(atm_range=20)
    legs = snapshot.get("chain", {}).get(trade["option_type"], [])
    leg = next((item for item in legs if int(item.get("strike", -1)) == int(trade["strike"])), None)
    if not leg or leg.get("ltp") is None:
        raise RuntimeError(f"No {trade['option_type']} quote for strike {trade['strike']}")
    timestamp = leg.get("quote_timestamp") or snapshot.get("timestamp")
    return float(leg["ltp"]), timestamp


def _close_if_required(trade: dict[str, Any], current_price: float, force_eod: bool = False) -> dict[str, Any]:
    reason = status = None
    if force_eod:
        reason, status = "END_OF_DAY", "CLOSED_EOD"
    elif current_price <= float(trade["stop_loss"]):
        reason, status = "STOP_LOSS", "CLOSED_SL"
    elif trade.get("target_2") and current_price >= float(trade["target_2"]):
        reason, status = "TARGET_2", "CLOSED_TARGET_2"
    elif trade.get("target_1") and current_price >= float(trade["target_1"]):
        reason, status = "TARGET_1", "CLOSED_TARGET_1"

    if not status:
        unrealized = round((current_price - trade["entry_price"]) * trade["quantity"], 2)
        store.record_paper_monitor_event(trade["id"], current_price, "HOLD", None)
        return {"action": "HOLD", "trade_id": trade["id"], "current_price": current_price,
                "unrealized_pnl": unrealized}

    turnover = (trade["entry_price"] + current_price) * trade["quantity"]
    estimated_costs = turnover * settings.paper_cost_rate
    closed = store.close_paper_trade(trade["id"], current_price, status, estimated_costs, reason)
    if closed is None:
        return {"action": "ALREADY_CLOSED", "trade_id": trade["id"]}
    store.record_trade_result(closed["net_pnl"], "B")
    store.record_paper_monitor_event(trade["id"], current_price, "CLOSED", reason)
    event = {"event": "PAPER_TRADE_CLOSED", "trade_id": trade["id"], "status": status,
             "reason": reason, "close_price": current_price, "net_pnl": closed["net_pnl"]}
    _write_notification(event)
    record_alert("INFO", "PAPER_TRADE_CLOSED", f"Paper trade {trade['id']} closed: {reason}")
    return {"action": "CLOSED", **closed}


def monitor_once(data_source: Any, now: datetime | None = None) -> dict[str, Any]:
    trade = store.get_open_paper_trade()
    with _lock:
        _state.iterations += 1
        _state.last_checked_at = datetime.now(timezone.utc).isoformat()
        _state.active_trade_id = trade["id"] if trade else None
    if not trade:
        with _lock:
            _state.last_action = "NO_OPEN_TRADE"
            _state.last_error = None
        return {"action": "NONE", "detail": "No open paper trade"}

    try:
        current_price, quote_timestamp = _option_price(data_source, trade)
        result = _close_if_required(trade, current_price, force_eod=_is_eod(now))
        with _lock:
            _state.successful_quotes += 1
            _state.last_price = current_price
            _state.last_action = result["action"]
            _state.last_error = None
        result["quote_timestamp"] = quote_timestamp
        return result
    except Exception as exc:
        message = str(exc)
        store.record_paper_monitor_event(trade["id"], None, "ERROR", message)
        with _lock:
            _state.quote_failures += 1
            _state.last_action = "ERROR"
            _state.last_error = message
        record_alert("AMBER", "PAPER_MONITOR_QUOTE_FAILURE", message)
        logger.exception("paper_monitor_iteration_failed", extra={"event": "paper_monitor_iteration_failed"})
        return {"action": "ERROR", "detail": message, "trade_id": trade["id"]}


def status_snapshot() -> dict[str, Any]:
    with _lock:
        return {**asdict(_state), "enabled": settings.paper_auto_monitor_enabled,
                "interval_sec": settings.paper_monitor_interval_sec,
                "eod_exit_time": settings.paper_eod_exit_time,
                "execution_mode": "PAPER_ONLY"}


async def run_monitor_loop(data_source_factory: Callable[[], Any]) -> None:
    with _lock:
        _state.running = True
    logger.info("paper_monitor_started", extra={"event": "paper_monitor_started"})
    try:
        while True:
            if settings.paper_auto_monitor_enabled:
                await asyncio.to_thread(monitor_once, data_source_factory())
            await asyncio.sleep(settings.paper_monitor_interval_sec)
    except asyncio.CancelledError:
        logger.info("paper_monitor_stopped", extra={"event": "paper_monitor_stopped"})
        raise
    finally:
        with _lock:
            _state.running = False
