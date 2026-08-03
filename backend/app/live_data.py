from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass
class FeedState:
    connected: bool = False
    last_tick_at: str | None = None
    reconnects: int = 0
    stale_events: int = 0
    instruments_synced: int = 0
    expiry: str | None = None
    message: str = "Feed not started"


_state = FeedState()
_lock = Lock()


def mark_snapshot(snapshot: dict[str, Any]) -> None:
    with _lock:
        _state.connected = True
        _state.last_tick_at = snapshot.get("timestamp") or datetime.now(timezone.utc).isoformat()
        options = snapshot.get("options") or {}
        _state.expiry = options.get("expiry")
        chain = options.get("chain") or {}
        _state.instruments_synced = len(chain.get("CE") or []) + len(chain.get("PE") or [])
        _state.message = "Latest REST snapshot received"


def mark_failure(message: str) -> None:
    with _lock:
        _state.connected = False
        _state.reconnects += 1
        _state.message = message[:300]


def status(max_age_sec: float = 15.0) -> dict[str, Any]:
    with _lock:
        payload = asdict(_state)
    age = None
    if payload["last_tick_at"]:
        try:
            ts = datetime.fromisoformat(payload["last_tick_at"].replace("Z", "+00:00"))
            age = max(0.0, (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds())
        except ValueError:
            age = None
    payload["age_sec"] = round(age, 2) if age is not None else None
    payload["fresh"] = bool(payload["connected"] and age is not None and age <= max_age_sec)
    payload["mode"] = "REST_POLLING_SAFE"
    payload["websocket_enabled"] = False
    return payload
