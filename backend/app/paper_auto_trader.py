"""Autonomous, fail-closed PAPER-only setup and entry worker.

The worker deliberately composes the existing live-intelligence, setup,
risk-supervisor and paper-ledger functions. It contains no broker order call.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app import store
from app.config import settings
from app.live_intelligence_history import trend
from app.live_intelligence import analyse_live_market
from app.live_intelligence_history import record_snapshot
from app.live_paper_bridge import build_paper_setup_candidate, prepare_paper_setup_from_preview
from app.market_clock import market_clock
from app.observability import record_alert
from app.risk_supervisor import evaluate_paper_entry

logger = logging.getLogger("vstradingai.paper_auto_trader")


@dataclass
class AutoTraderState:
    running: bool = False
    iterations: int = 0
    paper_trades_opened: int = 0
    blocked: int = 0
    last_checked_at: str | None = None
    last_action: str = "NOT_STARTED"
    last_reason: str | None = None
    last_setup_id: int | None = None
    last_trade_id: int | None = None


_state = AutoTraderState()
_lock = threading.RLock()


def _cutoff_reached(now: datetime) -> bool:
    hh, mm = (int(x) for x in settings.execution_entry_cutoff_time.split(":", 1))
    local = now.astimezone(ZoneInfo(settings.app_timezone))
    return (local.hour, local.minute) >= (hh, mm)


def _cooldown_active(now: datetime) -> bool:
    last = store.latest_closed_paper_trade()
    if not last or not last.get("closed_at") or settings.risk_cooldown_minutes <= 0:
        return False
    closed_at = datetime.fromisoformat(str(last["closed_at"]).replace("Z", "+00:00"))
    return (now.astimezone(timezone.utc) - closed_at.astimezone(timezone.utc)).total_seconds() < settings.risk_cooldown_minutes * 60


def _finish(action: str, reason: str | None = None, *, setup_id: int | None = None,
            trade_id: int | None = None, details: dict | None = None,
            cycle_key: str | None = None) -> dict[str, Any]:
    with _lock:
        changed = (_state.last_action, _state.last_reason) != (action, reason)
    # Persist every finalized-candle decision, plus state transitions such as
    # broker disconnection. Repeated closed-market/open-position polls remain
    # visible in memory without growing SQLite every 15 seconds.
    if cycle_key or changed:
        try:
            store.record_paper_automation_run(action, reason, setup_id, trade_id, details, cycle_key)
        except Exception as exc:
            # A unique cycle collision means another worker/restart already
            # handled this finalized candle. Never treat it as permission to
            # execute the paper entry twice.
            if cycle_key and "UNIQUE constraint failed" in str(exc):
                action, reason = "WAITING", "CANDLE_ALREADY_PROCESSED"
            else:
                raise
    with _lock:
        _state.last_action = action
        _state.last_reason = reason
        _state.last_setup_id = setup_id
        _state.last_trade_id = trade_id
        if action == "PAPER_TRADE_OPENED":
            _state.paper_trades_opened += 1
        elif action == "BLOCKED":
            _state.blocked += 1
    return {"action": action, "reason": reason, "setup_id": setup_id,
            "trade_id": trade_id, "details": details or {},
            "execution_mode": "PAPER_ONLY", "live_orders_enabled": False}


def _cycle_key(snapshot: dict[str, Any]) -> str | None:
    raw = snapshot.get("timestamp") or snapshot.get("captured_at")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None
    minute = dt.minute - (dt.minute % 3)
    return dt.replace(minute=minute, second=0, microsecond=0).isoformat()


def run_once(data_source: Any, now: datetime | None = None,
             trend_provider: Callable[..., dict] = trend) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    with _lock:
        _state.iterations += 1
        _state.last_checked_at = now.astimezone(timezone.utc).isoformat()

    if not settings.paper_auto_trader_enabled:
        return _finish("DISABLED", "PAPER_AUTO_TRADER_ENABLED=false")
    if settings.live_orders_enabled:
        return _finish("BLOCKED", "Safety invariant violated: LIVE_ORDERS_ENABLED must be false")

    clock = market_clock(now, settings.market_holidays, settings.market_open_time, settings.market_close_time)
    if not clock.market_open:
        return _finish("WAITING", clock.reason, details={"market_clock": clock.to_dict()})
    if _cutoff_reached(now):
        return _finish("WAITING", "ENTRY_CUTOFF_REACHED")
    if store.get_open_paper_trade():
        return _finish("WAITING", "PAPER_TRADE_ALREADY_OPEN")
    if _cooldown_active(now):
        return _finish("WAITING", "RISK_COOLDOWN_ACTIVE")

    try:
        snapshot = data_source.get_option_chain(atm_range=settings.paper_auto_trader_atm_range)
        cycle_key = _cycle_key(snapshot)
        if cycle_key and store.has_paper_automation_cycle(cycle_key):
            return _finish("WAITING", "CANDLE_ALREADY_PROCESSED")
        # The former manual preview depended on somebody opening the dashboard
        # to populate OI/PCR history. v7.8 records the sample itself, allowing
        # the autonomous loop to build directional evidence without UI traffic.
        record_snapshot(analyse_live_market(
            snapshot, max_age_sec=settings.paper_auto_trader_max_age_sec
        ))
        preview = build_paper_setup_candidate(
            snapshot, trend_provider(limit=60), max_age_sec=settings.paper_auto_trader_max_age_sec
        )
    except Exception as exc:
        message = f"BROKER_DATA_UNAVAILABLE: {type(exc).__name__}: {exc}"
        with _lock:
            repeated = _state.last_reason == message
        if not repeated:
            record_alert("AMBER", "PAPER_AUTO_TRADER_DATA_FAILURE", message)
        return _finish("BLOCKED", message)

    if preview.get("status") != "READY_FOR_HUMAN_REVIEW":
        blockers = preview.get("blockers") or [preview.get("status", "NOT_READY")]
        return _finish("NO_TRADE", "; ".join(str(x) for x in blockers),
                       details={"preview": preview}, cycle_key=cycle_key)

    candidate = preview["candidate"]
    allowed_grades = {x.strip() for x in settings.paper_auto_trader_grades.split(",") if x.strip()}
    if candidate.get("grade") not in allowed_grades:
        return _finish("NO_TRADE", f"GRADE_NOT_ALLOWED: {candidate.get('grade')}", cycle_key=cycle_key)
    if int(candidate.get("alignment_score") or 0) < settings.paper_auto_trader_min_score:
        return _finish("NO_TRADE", "ALIGNMENT_SCORE_BELOW_THRESHOLD",
                       details={"candidate": candidate}, cycle_key=cycle_key)

    prepared = prepare_paper_setup_from_preview(preview)
    setup = prepared.get("setup") or {}
    setup_id = setup.get("id")
    if not setup_id:
        return _finish("BLOCKED", "SETUP_PERSISTENCE_FAILED", cycle_key=cycle_key)
    if setup.get("status") == "GENERATED":
        try:
            setup = store.review_trade_setup(setup_id, "APPROVED", "v7.8 autonomous paper-only policy") or setup
        except ValueError as exc:
            return _finish("BLOCKED", str(exc), setup_id=setup_id, cycle_key=cycle_key)
    elif setup.get("status") != "APPROVED":
        return _finish("WAITING", f"DUPLICATE_SETUP_{setup.get('status')}",
                       setup_id=setup_id, cycle_key=cycle_key)

    entry_price = float(candidate["entry_reference"])
    risk = evaluate_paper_entry(setup, entry_price)
    if not risk.approved:
        return _finish("BLOCKED", "; ".join(risk.reasons), setup_id=setup_id,
                       details={"risk": risk.to_dict()}, cycle_key=cycle_key)
    try:
        trade_id = store.open_paper_trade(
            setup_id, risk.requested_quantity, entry_price, settings.paper_slippage_rupees
        )
        from app.paper_trade_management import ensure_management
        trade = store.get_open_paper_trade()
        if trade:
            ensure_management(trade)
    except Exception as exc:
        return _finish("BLOCKED", f"PAPER_OPEN_FAILED: {exc}", setup_id=setup_id,
                       cycle_key=cycle_key)

    record_alert("INFO", "AUTONOMOUS_PAPER_TRADE_OPENED", f"Paper trade {trade_id} opened from setup {setup_id}")
    return _finish("PAPER_TRADE_OPENED", "A/A+ policy and risk checks passed",
                   setup_id=setup_id, trade_id=trade_id,
                   details={"candidate": candidate, "risk": risk.to_dict()}, cycle_key=cycle_key)


def status_snapshot() -> dict[str, Any]:
    with _lock:
        state = asdict(_state)
    return {**state, "enabled": settings.paper_auto_trader_enabled,
            "interval_sec": settings.paper_auto_trader_interval_sec,
            "minimum_score": settings.paper_auto_trader_min_score,
            "allowed_grades": settings.paper_auto_trader_grades,
            "execution_mode": "PAPER_ONLY", "live_orders_enabled": False,
            "recent_runs": store.list_paper_automation_runs(limit=10)}


async def run_loop(data_source_factory: Callable[[], Any]) -> None:
    with _lock:
        _state.running = True
    logger.info("paper_auto_trader_started")
    try:
        while True:
            if settings.paper_auto_trader_enabled:
                await asyncio.to_thread(run_once, data_source_factory())
            await asyncio.sleep(settings.paper_auto_trader_interval_sec)
    except asyncio.CancelledError:
        logger.info("paper_auto_trader_stopped")
        raise
    finally:
        with _lock:
            _state.running = False
