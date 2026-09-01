"""Automatic live-session evidence recorder.

Collects safe operational evidence from the running market-data components at a
fixed interval. It never enables or submits broker orders.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable

from app.config import settings
from app.live_session_validation import LiveSessionValidation, SessionThresholds


class LiveSessionRecorder:
    def __init__(self, service: LiveSessionValidation, interval_sec: float = 30.0):
        self.service = service
        self.interval_sec = max(5.0, float(interval_sec))
        self.runs = 0
        self.recorded = 0
        self.failures = 0
        self.last_run_at: str | None = None
        self.last_recorded_at: str | None = None
        self.last_error: str | None = None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def build_payload(
        self,
        *,
        runtime_status: dict[str, Any],
        market_safety: dict[str, Any],
        tick_bridge_status: dict[str, Any],
    ) -> dict[str, Any]:
        blockers = list(market_safety.get("blockers") or [])
        warnings = list(market_safety.get("warnings") or [])
        last_error = runtime_status.get("last_error")
        errors = [str(last_error)] if last_error else []
        errors.extend(str(x) for x in blockers if x not in {"MARKET_CLOSED", "MARKET_NOT_OPEN"})
        age = market_safety.get("age_sec")
        if age is None:
            age = runtime_status.get("heartbeat_age_sec")
        return {
            "trading_day": market_safety.get("trading_day"),
            "feed_age_sec": float(age or 0.0),
            "websocket_connected": bool(runtime_status.get("connected")),
            "authenticated": bool(market_safety.get("authenticated", True)),
            "market_open": bool(market_safety.get("market_open", runtime_status.get("market_open", True))),
            "option_chain_ready": bool(market_safety.get("option_chain_ready", not blockers)),
            "tick_bridge_ready": not bool(tick_bridge_status.get("last_error")),
            "errors": errors + warnings[:5],
            "expiry": market_safety.get("expiry") or runtime_status.get("expiry") or "UNKNOWN",
            "market_regime": market_safety.get("market_regime") or runtime_status.get("market_regime") or "UNKNOWN",
        }

    def record_once(
        self,
        runtime_status: dict[str, Any],
        market_safety: dict[str, Any],
        tick_bridge_status: dict[str, Any],
    ) -> dict[str, Any]:
        self.runs += 1
        self.last_run_at = self._now()
        try:
            row = self.service.record(self.build_payload(
                runtime_status=runtime_status,
                market_safety=market_safety,
                tick_bridge_status=tick_bridge_status,
            ))
            self.recorded += 1
            self.last_recorded_at = row["captured_at"]
            self.last_error = None
            return row
        except Exception as exc:  # defensive operational loop
            self.failures += 1
            self.last_error = str(exc)[:500]
            raise

    async def run_loop(
        self,
        runtime_status_fn: Callable[[], dict[str, Any]],
        market_safety_fn: Callable[[], dict[str, Any]],
        tick_bridge_status_fn: Callable[[], dict[str, Any]],
    ) -> None:
        while True:
            try:
                self.record_once(runtime_status_fn(), market_safety_fn(), tick_bridge_status_fn())
            except Exception:
                pass
            await asyncio.sleep(self.interval_sec)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": bool(getattr(settings, "live_session_auto_record_enabled", True)),
            "interval_sec": self.interval_sec,
            "runs": self.runs,
            "recorded": self.recorded,
            "failures": self.failures,
            "last_run_at": self.last_run_at,
            "last_recorded_at": self.last_recorded_at,
            "last_error": self.last_error,
            "live_orders_enabled": False,
        }


_service = LiveSessionValidation(
    settings.live_session_validation_path,
    SessionThresholds(
        min_samples=settings.live_session_min_samples,
        min_ready_ratio=settings.live_session_min_ready_ratio,
        max_feed_age_sec=settings.live_session_max_feed_age_sec,
        max_error_ratio=settings.live_session_max_error_ratio,
    ),
)
_recorder: LiveSessionRecorder | None = None


def get_live_session_service() -> LiveSessionValidation:
    return _service


def get_live_session_recorder() -> LiveSessionRecorder:
    global _recorder
    if _recorder is None:
        _recorder = LiveSessionRecorder(_service, getattr(settings, "live_session_auto_record_interval_sec", 30.0))
    return _recorder
