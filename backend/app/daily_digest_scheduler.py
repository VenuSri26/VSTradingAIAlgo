"""Restart-safe daily operational digest scheduler.

Generates at most one digest per configured local trading day. A missed run is
caught up after restart once the configured time has passed. This component is
operational reporting only and never enables broker orders.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, time, timezone
from threading import RLock
from typing import Any
from zoneinfo import ZoneInfo


class DailyDigestScheduler:
    def __init__(self, digest, *, enabled: bool = True, run_time: str = "16:00", timezone_name: str = "Asia/Kolkata", poll_interval_sec: float = 60.0, enqueue: bool = True):
        self.digest = digest
        self.enabled = bool(enabled)
        self.run_time = self._parse_time(run_time)
        self.timezone_name = timezone_name
        self.tz = ZoneInfo(timezone_name)
        self.poll_interval_sec = max(10.0, float(poll_interval_sec))
        self.enqueue = bool(enqueue)
        self._lock = RLock()
        self._runs = 0
        self._skipped = 0
        self._last_run_at: str | None = None
        self._last_run_day: str | None = self._latest_day()
        self._last_error: str | None = None

    @staticmethod
    def _parse_time(value: str) -> time:
        try:
            hour, minute = [int(part) for part in value.strip().split(":", 1)]
            return time(hour=hour, minute=minute)
        except Exception as exc:
            raise ValueError("DAILY_DIGEST_TIME must use HH:MM 24-hour format") from exc

    def _latest_day(self) -> str | None:
        try:
            rows = self.digest.history(1)
            if not rows:
                return None
            generated = datetime.fromisoformat(rows[0]["generated_at"])
            if generated.tzinfo is None:
                generated = generated.replace(tzinfo=timezone.utc)
            return generated.astimezone(self.tz).date().isoformat()
        except Exception:
            return None

    def _now_local(self, now: datetime | None = None) -> datetime:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(self.tz)

    def due(self, now: datetime | None = None) -> bool:
        if not self.enabled:
            return False
        local = self._now_local(now)
        day = local.date().isoformat()
        return local.time().replace(tzinfo=None) >= self.run_time and self._last_run_day != day

    def run_once(self, now: datetime | None = None, *, force: bool = False) -> dict[str, Any]:
        local = self._now_local(now)
        day = local.date().isoformat()
        with self._lock:
            if not force and not self.due(local):
                self._skipped += 1
                return {"generated": False, "reason": "NOT_DUE", **self.status(local)}
            try:
                digest = self.digest.generate(enqueue=self.enqueue)
                self._runs += 1
                self._last_run_day = day
                self._last_run_at = datetime.now(timezone.utc).isoformat()
                self._last_error = None
                return {"generated": True, "digest": digest, **self.status(local)}
            except Exception as exc:
                self._last_error = str(exc)
                return {"generated": False, "reason": "ERROR", **self.status(local)}

    async def run_loop(self) -> None:
        while True:
            self.run_once()
            await asyncio.sleep(self.poll_interval_sec)

    def status(self, now: datetime | None = None) -> dict[str, Any]:
        local = self._now_local(now)
        next_day = local.date()
        if local.time().replace(tzinfo=None) >= self.run_time:
            from datetime import timedelta
            next_day += timedelta(days=1)
        next_local = datetime.combine(next_day, self.run_time, tzinfo=self.tz)
        return {
            "enabled": self.enabled,
            "configured_time": self.run_time.strftime("%H:%M"),
            "timezone": self.timezone_name,
            "enqueue": self.enqueue,
            "due_now": self.due(local),
            "next_run_at": next_local.astimezone(timezone.utc).isoformat(),
            "last_run_at": self._last_run_at,
            "last_run_day": self._last_run_day,
            "runs": self._runs,
            "skipped": self._skipped,
            "last_error": self._last_error,
            "live_orders_enabled": False,
        }
