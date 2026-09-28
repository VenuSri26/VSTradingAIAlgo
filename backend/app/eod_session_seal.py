"""Durable fail-closed end-of-day execution session seal."""
from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app import store
from app.config import settings
from app.execution_ledger import blocking_exposure, record_event
from app.execution_spine import reconcile_positions_once

IST = ZoneInfo("Asia/Kolkata")


def seal_session(*, broker: Any | None = None, now: datetime | None = None) -> dict[str, Any]:
    local = (now or datetime.now(timezone.utc)).astimezone(IST)
    hh, mm = (int(value) for value in settings.execution_eod_seal_time.split(":", 1))
    seal_at = datetime.combine(local.date(), time(hh, mm), tzinfo=IST)
    if local < seal_at:
        raise ValueError("EOD_SEAL_NOT_DUE")

    blockers: list[str] = []
    reconciliation = None
    if settings.is_live():
        if broker is None:
            blockers.append("BROKER_RECONCILIATION_REQUIRED")
        else:
            reconciliation = reconcile_positions_once(broker=broker)
            if not reconciliation["matched"]:
                blockers.append("BROKER_LOCAL_POSITION_MISMATCH")
    unresolved = blocking_exposure()
    if unresolved:
        blockers.append("UNRESOLVED_EXECUTION_EXPOSURE")
    if store.get_open_position() or store.get_open_paper_trade():
        blockers.append("POSITION_NOT_FLAT")

    sealed = not blockers
    result = {
        "trading_day": local.date().isoformat(), "sealed": sealed,
        "sealed_at": local.isoformat(), "blockers": blockers,
        "unresolved_execution_ids": [item["execution_id"] for item in unresolved],
        "broker_reconciliation": reconciliation,
    }
    if not sealed:
        store.set_kill_switch(True, "EOD session seal blocked: " + ",".join(blockers))
    record_event(None, "EOD_SESSION_SEALED" if sealed else "EOD_SESSION_SEAL_BLOCKED", result)
    return result
