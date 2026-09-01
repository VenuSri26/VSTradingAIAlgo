from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.market_clock import parse_timestamp


@dataclass(frozen=True)
class FeedAlert:
    code: str
    severity: str
    message: str
    action: str


def _age_sec(value: str | None, now: datetime) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, (now - parse_timestamp(value)).total_seconds())
    except (TypeError, ValueError):
        return None


def evaluate_feed_alerts(
    state: dict[str, Any],
    *,
    now: str | datetime | None = None,
    stale_after_sec: float = 15.0,
    token_warn_age_sec: float = 3600.0,
    token_block_age_sec: float = 43200.0,
) -> dict[str, Any]:
    now_dt = parse_timestamp(now)
    market_age = _age_sec(state.get("last_market_timestamp") or state.get("last_success_at"), now_dt)
    token_age = _age_sec(state.get("token_checked_at"), now_dt)
    alerts: list[FeedAlert] = []

    if not state.get("authenticated"):
        alerts.append(FeedAlert("BROKER_AUTH_FAILED", "CRITICAL", "Broker authentication is unhealthy", "REFRESH_KITE_TOKEN"))
    if not state.get("connected"):
        alerts.append(FeedAlert("FEED_DISCONNECTED", "CRITICAL", "Market feed is disconnected", "RECONNECT_OR_USE_REST_FALLBACK"))
    if market_age is None:
        alerts.append(FeedAlert("NO_MARKET_TIMESTAMP", "CRITICAL", "No exchange timestamp is available", "BLOCK_TRADING"))
    elif market_age > stale_after_sec:
        alerts.append(FeedAlert("STALE_MARKET_DATA", "CRITICAL", f"Market data is stale by {market_age:.1f} seconds", "BLOCK_TRADING"))
    failures = int(state.get("consecutive_failures") or 0)
    if failures >= 3:
        alerts.append(FeedAlert("REPEATED_FEED_FAILURES", "CRITICAL", f"Feed has {failures} consecutive failures", "RESTART_MARKET_DATA_SERVICE"))
    elif failures:
        alerts.append(FeedAlert("RECENT_FEED_FAILURE", "WARNING", f"Feed has {failures} recent failure(s)", "WATCH_FEED"))
    if token_age is None:
        alerts.append(FeedAlert("TOKEN_NOT_CHECKED", "WARNING", "Broker token health has not been checked", "CHECK_TOKEN"))
    elif token_age >= token_block_age_sec:
        alerts.append(FeedAlert("TOKEN_CHECK_EXPIRED", "CRITICAL", f"Token health is {token_age / 3600:.1f} hours old", "REFRESH_KITE_TOKEN"))
    elif token_age >= token_warn_age_sec:
        alerts.append(FeedAlert("TOKEN_CHECK_STALE", "WARNING", f"Token health is {token_age / 3600:.1f} hours old", "CHECK_TOKEN"))
    if state.get("websocket_requested") and not state.get("websocket_active"):
        alerts.append(FeedAlert("WEBSOCKET_FALLBACK", "WARNING", "WebSocket is requested but REST fallback is active", "CHECK_WEBSOCKET"))
    if not state.get("expiry"):
        alerts.append(FeedAlert("EXPIRY_UNAVAILABLE", "WARNING", "Current option expiry is unavailable", "SYNC_INSTRUMENTS"))
    if int(state.get("instruments_synced") or 0) <= 0:
        alerts.append(FeedAlert("INSTRUMENTS_NOT_SYNCED", "WARNING", "Instrument master is not synchronized", "SYNC_INSTRUMENTS"))

    critical = sum(1 for item in alerts if item.severity == "CRITICAL")
    warning = sum(1 for item in alerts if item.severity == "WARNING")
    status = "BLOCKED" if critical else ("DEGRADED" if warning else "READY")
    return {
        "status": status,
        "critical_count": critical,
        "warning_count": warning,
        "market_age_sec": round(market_age, 2) if market_age is not None else None,
        "token_check_age_sec": round(token_age, 2) if token_age is not None else None,
        "alerts": [asdict(item) for item in alerts],
        "recommended_action": "NO_TRADE" if critical else "ALLOW_DECISION_SUPPORT",
        "live_orders_enabled": False,
        "evaluated_at": now_dt.astimezone(timezone.utc).isoformat(),
    }


class FeedAlertHistory:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = Lock()

    def record(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "evaluated_at": payload.get("evaluated_at"),
            "status": payload.get("status"),
            "critical_count": payload.get("critical_count"),
            "warning_count": payload.get("warning_count"),
            "alerts": payload.get("alerts", []),
        }
        signature = json.dumps({"status": row["status"], "alerts": row["alerts"]}, sort_keys=True)
        with self._lock:
            previous = None
            if self.path.exists():
                try:
                    last = self.path.read_text().splitlines()[-1]
                    previous_row = json.loads(last)
                    previous = json.dumps({"status": previous_row.get("status"), "alerts": previous_row.get("alerts", [])}, sort_keys=True)
                except (OSError, ValueError, IndexError):
                    previous = None
            if signature == previous:
                return
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text().splitlines()[-max(1, min(limit, 500)):]:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
        return list(reversed(rows))
