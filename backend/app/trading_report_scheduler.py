"""Restart-safe schedulers for pre-market and post-market trading reports."""
from __future__ import annotations

import asyncio
from datetime import datetime, time, timezone
from threading import RLock
from zoneinfo import ZoneInfo

from app.config import settings
from app.market_clock import market_clock


class TradingReportScheduler:
    def __init__(self, service, report_type: str, run_time: str, *, enabled: bool = True,
                 timezone_name: str = "Asia/Kolkata", poll_interval_sec: float = 60):
        self.service = service
        self.report_type = report_type
        hour, minute = (int(x) for x in run_time.split(":", 1))
        self.run_time = time(hour, minute)
        self.enabled = enabled
        self.tz = ZoneInfo(timezone_name)
        self.poll_interval_sec = max(10.0, poll_interval_sec)
        self._lock = RLock()
        latest = service.latest(report_type)
        self.last_run_day = latest.get("trading_day") if latest else None
        self.last_run_at = latest.get("generated_at") if latest else None
        self.last_error: str | None = None

    def _local(self, now: datetime | None) -> datetime:
        value = now or datetime.now(timezone.utc)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self.tz)

    def due(self, now: datetime | None = None) -> bool:
        local = self._local(now)
        clock = market_clock(local, settings.market_holidays, settings.market_open_time, settings.market_close_time)
        session_allowed = clock.session == "PRE_OPEN" if self.report_type == "PRE_MARKET" else clock.session == "POST_CLOSE"
        return (self.enabled and session_allowed
                and local.time().replace(tzinfo=None) >= self.run_time
                and self.last_run_day != local.date().isoformat())

    def run_once(self, now: datetime | None = None, *, force: bool = False) -> dict:
        local = self._local(now)
        with self._lock:
            if not force and not self.due(local):
                return {"generated": False, "reason": "NOT_DUE", **self.status(local)}
            try:
                report = self.service.generate(self.report_type, local)
                self.last_run_day = report["trading_day"]
                self.last_run_at = report["generated_at"]
                self.last_error = None
                return {"generated": True, "report": report, **self.status(local)}
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                return {"generated": False, "reason": "ERROR", **self.status(local)}

    def status(self, now: datetime | None = None) -> dict:
        local = self._local(now)
        return {"report_type": self.report_type, "enabled": self.enabled,
                "configured_time": self.run_time.strftime("%H:%M"), "timezone": str(self.tz),
                "due_now": self.due(local), "last_run_day": self.last_run_day,
                "last_run_at": self.last_run_at, "last_error": self.last_error,
                "read_only_broker_access": True, "live_orders_enabled": False}

    async def run_loop(self) -> None:
        while True:
            self.run_once()
            await asyncio.sleep(self.poll_interval_sec)
