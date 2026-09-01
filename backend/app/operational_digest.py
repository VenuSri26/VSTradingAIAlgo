"""Daily operational digest for VSTradingAI.

The digest summarizes notification delivery, market calendar and broker-Greeks
validation. It is operational reporting only and can never enable live orders.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


class OperationalDigestService:
    def __init__(self, path: str, delivery, calendar, greeks_history, scheduler):
        self.path = Path(path)
        self.delivery = delivery
        self.calendar = calendar
        self.greeks_history = greeks_history
        self.scheduler = scheduler
        self._lock = RLock()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def _append(self, row: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")

    def build(self) -> dict[str, Any]:
        outbox = self.delivery.list(500)
        counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        for row in outbox:
            status = str(row.get("status") or "UNKNOWN").upper()
            severity = str(row.get("severity") or "INFO").upper()
            counts[status] = counts.get(status, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        delivery_status = self.delivery.status()
        calendar = self.calendar.status()
        greeks = self.greeks_history.summary()
        scheduler = self.scheduler.status()
        blockers: list[str] = []
        warnings: list[str] = []
        if counts.get("FAILED", 0):
            blockers.append("FAILED_NOTIFICATIONS_PRESENT")
        if counts.get("PENDING", 0) > 20:
            warnings.append("NOTIFICATION_BACKLOG_HIGH")
        if not delivery_status.get("delivery_enabled"):
            warnings.append("DELIVERY_CHANNEL_NOT_CONFIGURED")
        if calendar.get("count", 0) == 0:
            warnings.append("MARKET_CALENDAR_EMPTY")
        if greeks.get("samples", 0) < 5:
            warnings.append("INSUFFICIENT_GREEKS_VALIDATION_SAMPLES")
        status = "BLOCKED" if blockers else ("DEGRADED" if warnings else "READY")
        return {
            "generated_at": self._now(),
            "status": status,
            "notification_counts": counts,
            "severity_counts": severity_counts,
            "delivery": delivery_status,
            "scheduler": {
                "runs": scheduler.get("runs", 0),
                "delivered": scheduler.get("delivered", 0),
                "failed": scheduler.get("failed", 0),
                "escalated": scheduler.get("escalated", 0),
                "last_run_at": scheduler.get("last_run_at"),
            },
            "market_calendar": calendar,
            "greeks_validation": greeks,
            "blockers": blockers,
            "warnings": warnings,
            "recommended_action": "REVIEW_BLOCKERS" if blockers else ("REVIEW_WARNINGS" if warnings else "NO_ACTION"),
            "live_orders_enabled": False,
        }

    def generate(self, enqueue: bool = False) -> dict[str, Any]:
        digest = self.build()
        with self._lock:
            self._append(digest)
        if enqueue:
            sev = "CRITICAL" if digest["status"] == "BLOCKED" else ("WARNING" if digest["status"] == "DEGRADED" else "INFO")
            self.delivery.enqueue(
                "DAILY_OPERATIONAL_DIGEST",
                sev,
                f"Operational digest status {digest['status']}: {len(digest['blockers'])} blockers, {len(digest['warnings'])} warnings",
                digest["recommended_action"],
                {"digest": digest},
            )
        return digest

    def history(self, limit: int = 30) -> list[dict[str, Any]]:
        return list(reversed(self._read()[-max(1, min(int(limit), 365)):]))

    def status(self) -> dict[str, Any]:
        rows = self._read()
        latest = rows[-1] if rows else None
        return {
            "history_count": len(rows),
            "latest": latest,
            "digest_path": str(self.path),
            "live_orders_enabled": False,
        }
