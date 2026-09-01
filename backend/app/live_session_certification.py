"""Cross-session certification for live market-data reliability.

This module certifies operational evidence only. It never enables broker order
submission and always reports ``live_orders_enabled=False``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from app.live_session_validation import LiveSessionValidation


@dataclass(frozen=True)
class CertificationThresholds:
    min_sessions: int = 5
    min_ready_session_ratio: float = 0.80
    min_average_ready_ratio: float = 0.95
    min_average_websocket_ratio: float = 0.80
    max_average_error_ratio: float = 0.05
    max_average_feed_age_sec: float = 10.0


class LiveSessionCertification:
    def __init__(
        self,
        service: LiveSessionValidation,
        thresholds: CertificationThresholds | None = None,
        enqueue_fn: Callable[..., dict[str, Any]] | None = None,
    ):
        self.service = service
        self.thresholds = thresholds or CertificationThresholds()
        self.enqueue_fn = enqueue_fn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def evaluate(self, limit_days: int = 30) -> dict[str, Any]:
        report = self.service.multi_session_report(limit_days)
        sessions = list(report.get("sessions") or [])
        count = len(sessions)
        ready_count = sum(1 for s in sessions if s.get("status") == "READY")
        avg_ready = sum(float(s.get("ready_ratio") or 0.0) for s in sessions) / count if count else 0.0
        avg_ws = sum(float(s.get("websocket_ratio") or 0.0) for s in sessions) / count if count else 0.0
        avg_error = sum(float(s.get("error_ratio") or 0.0) for s in sessions) / count if count else 0.0
        avg_age = sum(float(s.get("average_feed_age_sec") or 0.0) for s in sessions) / count if count else 0.0
        ready_session_ratio = ready_count / count if count else 0.0

        blockers: list[str] = []
        warnings: list[str] = []
        t = self.thresholds
        if count < t.min_sessions:
            blockers.append("INSUFFICIENT_VALIDATED_SESSIONS")
        if count and ready_session_ratio < t.min_ready_session_ratio:
            blockers.append("READY_SESSION_RATIO_BELOW_TARGET")
        if count and avg_ready < t.min_average_ready_ratio:
            blockers.append("AVERAGE_READY_RATIO_BELOW_TARGET")
        if count and avg_error > t.max_average_error_ratio:
            blockers.append("AVERAGE_ERROR_RATIO_ABOVE_TARGET")
        if count and avg_age > t.max_average_feed_age_sec:
            blockers.append("AVERAGE_FEED_AGE_ABOVE_TARGET")
        if count and avg_ws < t.min_average_websocket_ratio:
            warnings.append("AVERAGE_WEBSOCKET_RATIO_BELOW_TARGET")

        status = "BLOCKED" if blockers else ("DEGRADED" if warnings else "CERTIFIED")
        return {
            "status": status,
            "evaluated_at": self._now(),
            "session_count": count,
            "ready_session_count": ready_count,
            "ready_session_ratio": round(ready_session_ratio, 4),
            "average_ready_ratio": round(avg_ready, 4),
            "average_websocket_ratio": round(avg_ws, 4),
            "average_error_ratio": round(avg_error, 4),
            "average_feed_age_sec": round(avg_age, 3),
            "thresholds": t.__dict__,
            "blockers": blockers,
            "warnings": warnings,
            "recommended_action": (
                "EVIDENCE_CERTIFIED_FOR_CONTROLLED_PAPER_PILOT"
                if status == "CERTIFIED"
                else "CONTINUE_MULTI_SESSION_VALIDATION"
            ),
            "sessions": sessions,
            "live_orders_enabled": False,
        }


    def breakdown(self, limit_days: int = 30) -> dict[str, Any]:
        rows = self.service.history(limit=5000)
        allowed_days = {s.get("trading_day") for s in self.service.multi_session_report(limit_days).get("sessions", [])}
        rows = [r for r in rows if r.get("trading_day") in allowed_days]

        def group(field: str) -> list[dict[str, Any]]:
            grouped: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                grouped.setdefault(str(row.get(field) or "UNKNOWN"), []).append(row)
            result = []
            for key, items in sorted(grouped.items()):
                count = len(items)
                ready = sum(1 for x in items if x.get("ready"))
                ws = sum(1 for x in items if x.get("websocket_connected"))
                errors = sum(1 for x in items if x.get("errors"))
                age = sum(float(x.get("feed_age_sec") or 0) for x in items) / count if count else 0.0
                result.append({
                    field: key, "samples": count,
                    "ready_ratio": round(ready / count, 4) if count else 0.0,
                    "websocket_ratio": round(ws / count, 4) if count else 0.0,
                    "error_ratio": round(errors / count, 4) if count else 0.0,
                    "average_feed_age_sec": round(age, 3),
                    "status": "READY" if count and ready == count and not errors else "REVIEW",
                })
            return result

        return {
            "by_expiry": group("expiry"),
            "by_market_regime": group("market_regime"),
            "sample_count": len(rows),
            "live_orders_enabled": False,
        }

    def enqueue_report(self, limit_days: int = 30) -> dict[str, Any]:
        result = self.evaluate(limit_days)
        if self.enqueue_fn is None:
            return {"enqueued": False, "reason": "NOTIFICATION_OUTBOX_UNAVAILABLE", "certification": result}
        severity = "INFO" if result["status"] == "CERTIFIED" else ("WARNING" if result["status"] == "DEGRADED" else "CRITICAL")
        message = (
            f"Live-session certification {result['status']}: "
            f"{result['ready_session_count']}/{result['session_count']} sessions ready, "
            f"average ready ratio {result['average_ready_ratio']:.1%}."
        )
        item = self.enqueue_fn(
            "LIVE_SESSION_CERTIFICATION",
            severity,
            message,
            result["recommended_action"],
            {"category": "INFRASTRUCTURE", "certification": result},
        )
        return {"enqueued": True, "notification": item, "certification": result}
