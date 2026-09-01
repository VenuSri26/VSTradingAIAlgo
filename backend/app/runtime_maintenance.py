"""Periodic Kite runtime maintenance and notification delivery.

Keeps active-expiry subscriptions fresh, handles expiry rollover, avoids false
heartbeat failures outside market hours, and persists token/feed notifications.
This module transports market data only and never enables broker orders.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from app.config import settings
from app.market_clock import market_clock


@dataclass
class MaintenanceState:
    running: bool = False
    last_run_at: str | None = None
    last_sync_at: str | None = None
    last_expiry: str | None = None
    sync_count: int = 0
    rollover_count: int = 0
    notification_count: int = 0
    last_notification_code: str | None = None
    last_error: str | None = None
    next_run_in_sec: float = 0.0


class RuntimeMaintenance:
    def __init__(self, *, interval_sec: float, notification_path: str):
        self.interval_sec = max(30.0, float(interval_sec))
        self.notification_path = Path(notification_path)
        self._state = MaintenanceState(next_run_in_sec=self.interval_sec)
        self._lock = RLock()
        self._last_codes: set[str] = set()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _write_notification(self, code: str, severity: str, message: str, action: str) -> None:
        # Active-state deduplication: repeated monitor cycles do not spam the log.
        if code in self._last_codes:
            return
        self._last_codes.add(code)
        self.notification_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": self._now().isoformat(), "code": code,
            "severity": severity, "message": message, "action": action,
            "live_orders_enabled": False,
        }
        with self.notification_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
        with self._lock:
            self._state.notification_count += 1
            self._state.last_notification_code = code

    def _clear_resolved(self, active_codes: set[str]) -> None:
        self._last_codes.intersection_update(active_codes)

    @staticmethod
    def _contracts(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for option_type in ("CE", "PE"):
            for item in snapshot.get("chain", {}).get(option_type, []):
                token = item.get("instrument_token")
                if not token:
                    continue
                result.append({
                    "instrument_token": token,
                    "tradingsymbol": item.get("tradingsymbol"),
                    "option_type": option_type,
                    "strike": item.get("strike"),
                    "expiry": snapshot.get("expiry"),
                })
        return result

    def run_once(self, data_source, runtime, feed_status: dict[str, Any] | None = None,
                 now: datetime | None = None) -> dict[str, Any]:
        now = now or self._now()
        clock = market_clock(now, settings.market_holidays, settings.market_open_time, settings.market_close_time)
        active_codes: set[str] = set()
        try:
            # Outside regular hours: do not treat an idle socket as a heartbeat outage.
            runtime.set_market_session(clock.market_open, clock.session)
            should_sync = runtime.status().get("metadata_count", 0) == 0
            last_sync = self._state.last_sync_at
            should_sync = should_sync or not last_sync
            if last_sync:
                last_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
                age_hours = (now - last_dt.astimezone(timezone.utc)).total_seconds() / 3600
                should_sync = should_sync or age_hours >= settings.instrument_sync_interval_hours
            if clock.market_open and should_sync:
                snapshot = data_source.get_option_chain(atm_range=settings.websocket_atm_range)
                expiry = str(snapshot.get("expiry") or "") or None
                old_expiry = self._state.last_expiry
                runtime.configure_contracts(self._contracts(snapshot))
                with self._lock:
                    self._state.last_sync_at = now.isoformat()
                    self._state.sync_count += 1
                    self._state.last_expiry = expiry
                    if old_expiry and expiry and old_expiry != expiry:
                        self._state.rollover_count += 1
                        self._write_notification(
                            "EXPIRY_ROLLOVER", "INFO",
                            f"Subscriptions rolled from {old_expiry} to {expiry}",
                            "VERIFY_ACTIVE_EXPIRY",
                        )
            status = feed_status or {}
            token_age = status.get("token_check_age_sec")
            authenticated = status.get("authenticated", True)
            if not authenticated:
                active_codes.add("KITE_AUTH_INVALID")
                self._write_notification("KITE_AUTH_INVALID", "CRITICAL", "Kite authentication is invalid", "REFRESH_KITE_TOKEN")
            elif token_age is not None and float(token_age) >= settings.token_block_age_sec:
                active_codes.add("KITE_TOKEN_STALE")
                self._write_notification("KITE_TOKEN_STALE", "CRITICAL", f"Token health check is {token_age}s old", "REFRESH_KITE_TOKEN")
            elif token_age is not None and float(token_age) >= settings.token_warn_age_sec:
                active_codes.add("KITE_TOKEN_WARNING")
                self._write_notification("KITE_TOKEN_WARNING", "WARNING", f"Token health check is {token_age}s old", "VERIFY_KITE_TOKEN")
            self._clear_resolved(active_codes)
            with self._lock:
                self._state.last_run_at = now.isoformat()
                self._state.last_error = None
                self._state.next_run_in_sec = self.interval_sec
        except Exception as exc:
            with self._lock:
                self._state.last_run_at = now.isoformat()
                self._state.last_error = str(exc)[:500]
            active_codes.add("MAINTENANCE_FAILURE")
            self._write_notification("MAINTENANCE_FAILURE", "WARNING", str(exc)[:300], "CHECK_RUNTIME_LOGS")
        return self.status(clock=clock.to_dict(), runtime=runtime.status())

    async def run_loop(self, data_source_factory: Callable[[], Any], runtime, feed_status_factory: Callable[[], dict[str, Any]] | None = None) -> None:
        with self._lock:
            self._state.running = True
        try:
            while True:
                feed = feed_status_factory() if feed_status_factory else None
                self.run_once(data_source_factory(), runtime, feed)
                await asyncio.sleep(self.interval_sec)
        finally:
            with self._lock:
                self._state.running = False

    def notifications(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.notification_path.exists():
            return []
        rows = []
        for line in self.notification_path.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 500)):]:
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: continue
        return list(reversed(rows))

    def status(self, *, clock: dict[str, Any] | None = None, runtime: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            payload = asdict(self._state)
        payload.update({
            "interval_sec": self.interval_sec,
            "market_clock": clock,
            "runtime": runtime,
            "notification_path": str(self.notification_path),
            "execution_mode": "MARKET_DATA_MAINTENANCE_ONLY",
            "live_orders_enabled": False,
        })
        return payload


_service: RuntimeMaintenance | None = None

def get_runtime_maintenance() -> RuntimeMaintenance:
    global _service
    if _service is None:
        _service = RuntimeMaintenance(
            interval_sec=settings.websocket_subscription_refresh_sec,
            notification_path=settings.runtime_notification_path,
        )
    return _service
