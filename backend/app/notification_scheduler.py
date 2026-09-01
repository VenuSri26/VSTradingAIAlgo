"""Background notification dispatch, retry, escalation and acknowledgement.

This service is operational only. It cannot enable broker execution.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class SchedulerState:
    runs: int = 0
    dispatched: int = 0
    delivered: int = 0
    failed: int = 0
    escalated: int = 0
    last_run_at: str | None = None
    last_error: str | None = None


class NotificationScheduler:
    def __init__(self, delivery, interval_sec: float = 60.0, escalate_after_sec: float = 900.0):
        self.delivery = delivery
        self.interval_sec = max(10.0, float(interval_sec))
        self.escalate_after_sec = max(60.0, float(escalate_after_sec))
        self.state = SchedulerState()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def run_once(self) -> dict[str, Any]:
        try:
            escalation = self.delivery.escalate_pending(self.escalate_after_sec)
            result = self.delivery.dispatch(limit=100)
            self.state.runs += 1
            self.state.dispatched += int(result.get("processed") or 0)
            self.state.delivered += int(result.get("delivered") or 0)
            self.state.failed += int(result.get("failed") or 0)
            self.state.escalated += int(escalation.get("escalated") or 0)
            self.state.last_run_at = self._now()
            self.state.last_error = None
            return {**self.status(), "run": result, "escalation": escalation}
        except Exception as exc:
            self.state.runs += 1
            self.state.last_run_at = self._now()
            self.state.last_error = str(exc)[:300]
            return self.status()

    async def run_loop(self) -> None:
        while True:
            self.run_once()
            await asyncio.sleep(self.interval_sec)

    def status(self) -> dict[str, Any]:
        return {
            **asdict(self.state),
            "interval_sec": self.interval_sec,
            "escalate_after_sec": self.escalate_after_sec,
            "outbox": self.delivery.status(),
            "live_orders_enabled": False,
        }
