"""Persistent live-session evidence recorder and readiness evaluator.

Records market-hour validation samples without enabling broker execution.  The
service is deliberately broker-agnostic so AWS live sessions can be audited
before any controlled execution pilot is considered.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class SessionThresholds:
    min_samples: int = 20
    min_ready_ratio: float = 0.95
    max_feed_age_sec: float = 10.0
    max_error_ratio: float = 0.05


class LiveSessionValidation:
    def __init__(self, path: str, thresholds: SessionThresholds | None = None):
        self.path = Path(path)
        self.thresholds = thresholds or SessionThresholds()
        self._lock = RLock()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
            except json.JSONDecodeError:
                continue
        return rows

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8")

    def record(self, payload: dict[str, Any]) -> dict[str, Any]:
        feed_age = float(payload.get("feed_age_sec") or 0.0)
        websocket_connected = bool(payload.get("websocket_connected"))
        authenticated = bool(payload.get("authenticated", True))
        market_open = bool(payload.get("market_open", True))
        option_chain_ready = bool(payload.get("option_chain_ready"))
        tick_bridge_ready = bool(payload.get("tick_bridge_ready"))
        errors = [str(x)[:200] for x in (payload.get("errors") or [])]
        blockers: list[str] = []
        if not authenticated: blockers.append("BROKER_AUTHENTICATION_INVALID")
        if not market_open: blockers.append("MARKET_NOT_OPEN")
        if feed_age > self.thresholds.max_feed_age_sec: blockers.append("FEED_STALE")
        if not option_chain_ready: blockers.append("OPTION_CHAIN_NOT_READY")
        if not tick_bridge_ready: blockers.append("TICK_BRIDGE_NOT_READY")
        if errors: blockers.append("RUNTIME_ERRORS_PRESENT")
        row = {
            "captured_at": self._now(),
            "trading_day": str(payload.get("trading_day") or datetime.now().date().isoformat()),
            "feed_age_sec": round(feed_age, 3),
            "websocket_connected": websocket_connected,
            "authenticated": authenticated,
            "market_open": market_open,
            "option_chain_ready": option_chain_ready,
            "tick_bridge_ready": tick_bridge_ready,
            "errors": errors,
            "blockers": blockers,
            "ready": not blockers,
            "transport": "WEBSOCKET" if websocket_connected else "REST_FALLBACK",
            "expiry": str(payload.get("expiry") or "UNKNOWN"),
            "market_regime": str(payload.get("market_regime") or "UNKNOWN"),
            "live_orders_enabled": False,
        }
        with self._lock:
            rows = self._read(); rows.append(row); self._write(rows[-5000:])
        return row

    def history(self, limit: int = 200, trading_day: str | None = None) -> list[dict[str, Any]]:
        rows = self._read()
        if trading_day:
            rows = [r for r in rows if r.get("trading_day") == trading_day]
        return rows[-max(1, min(int(limit), 1000)):]

    def multi_session_report(self, limit_days: int = 10) -> dict[str, Any]:
        rows = self._read()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            day = str(row.get("trading_day") or "UNKNOWN")
            grouped.setdefault(day, []).append(row)
        days = sorted(grouped)[-max(1, min(int(limit_days), 60)):]
        sessions = []
        for day in days:
            day_rows = grouped[day]
            count = len(day_rows)
            ready = sum(1 for r in day_rows if r.get("ready"))
            errors = sum(1 for r in day_rows if r.get("errors"))
            ws = sum(1 for r in day_rows if r.get("websocket_connected"))
            avg_age = sum(float(r.get("feed_age_sec") or 0) for r in day_rows) / count if count else 0.0
            sessions.append({
                "trading_day": day,
                "samples": count,
                "ready_ratio": round(ready / count, 4) if count else 0.0,
                "error_ratio": round(errors / count, 4) if count else 0.0,
                "websocket_ratio": round(ws / count, 4) if count else 0.0,
                "average_feed_age_sec": round(avg_age, 3),
                "status": "READY" if count >= self.thresholds.min_samples and ready / count >= self.thresholds.min_ready_ratio and errors / count <= self.thresholds.max_error_ratio else "NOT_READY",
            })
        ready_sessions = sum(1 for s in sessions if s["status"] == "READY")
        return {
            "sessions": sessions,
            "session_count": len(sessions),
            "ready_session_count": ready_sessions,
            "ready_session_ratio": round(ready_sessions / len(sessions), 4) if sessions else 0.0,
            "recommended_action": "MULTI_SESSION_EVIDENCE_READY_FOR_REVIEW" if sessions and ready_sessions == len(sessions) else "CONTINUE_LIVE_SESSION_VALIDATION",
            "live_orders_enabled": False,
        }

    def summary(self, limit: int = 500, trading_day: str | None = None) -> dict[str, Any]:
        rows = self.history(limit, trading_day)
        count = len(rows)
        ready = sum(1 for r in rows if r.get("ready"))
        error_samples = sum(1 for r in rows if r.get("errors"))
        ws_samples = sum(1 for r in rows if r.get("websocket_connected"))
        ready_ratio = ready / count if count else 0.0
        error_ratio = error_samples / count if count else 0.0
        avg_age = sum(float(r.get("feed_age_sec") or 0) for r in rows) / count if count else None
        blockers: list[str] = []
        warnings: list[str] = []
        if count < self.thresholds.min_samples:
            blockers.append("INSUFFICIENT_LIVE_SESSION_SAMPLES")
        if count and ready_ratio < self.thresholds.min_ready_ratio:
            blockers.append("LIVE_SESSION_READY_RATIO_BELOW_TARGET")
        if count and error_ratio > self.thresholds.max_error_ratio:
            blockers.append("LIVE_SESSION_ERROR_RATIO_ABOVE_TARGET")
        if count and ws_samples == 0:
            warnings.append("NO_WEBSOCKET_SAMPLES_RECORDED")
        status = "BLOCKED" if blockers else ("DEGRADED" if warnings else "READY")
        return {
            "status": status,
            "samples": count,
            "ready_samples": ready,
            "ready_ratio": round(ready_ratio, 4),
            "error_ratio": round(error_ratio, 4),
            "websocket_ratio": round(ws_samples / count, 4) if count else 0.0,
            "average_feed_age_sec": round(avg_age, 3) if avg_age is not None else None,
            "thresholds": self.thresholds.__dict__,
            "blockers": blockers,
            "warnings": warnings,
            "recommended_action": "CONTINUE_PAPER_VALIDATION" if status != "READY" else "SESSION_EVIDENCE_READY_FOR_REVIEW",
            "live_orders_enabled": False,
        }
