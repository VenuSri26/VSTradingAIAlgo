"""KiteTicker-ready stream manager with restart-safe control state.

This module deliberately separates transport lifecycle from trade logic. Incoming
batches are normalized and forwarded to the existing TickBridge. Broker order
submission is never performed here.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable


@dataclass
class StreamState:
    requested: bool = False
    connected: bool = False
    mode: str = "REST_FALLBACK"
    reconnect_attempts: int = 0
    last_connected_at: str | None = None
    last_disconnected_at: str | None = None
    last_batch_at: str | None = None
    last_error: str | None = None
    subscribed_tokens: list[int] = field(default_factory=list)
    received_batches: int = 0
    received_ticks: int = 0
    accepted_ticks: int = 0
    ignored_ticks: int = 0
    rejected_ticks: int = 0
    dropped_ticks: int = 0


class KiteStreamManager:
    def __init__(self, *, requested: bool, max_batch_size: int = 200, max_queue_size: int = 2000):
        self.max_batch_size = max(1, max_batch_size)
        self.max_queue_size = max(self.max_batch_size, max_queue_size)
        self._lock = RLock()
        self._state = StreamState(requested=requested, mode="WEBSOCKET_PENDING" if requested else "REST_FALLBACK")
        self._recent_batches: deque[dict[str, Any]] = deque(maxlen=100)

    def subscribe(self, tokens: list[int]) -> dict[str, Any]:
        clean = sorted({int(token) for token in tokens if int(token) > 0})
        with self._lock:
            self._state.subscribed_tokens = clean
        return self.status()

    def mark_connected(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._state.connected = True
            self._state.mode = "WEBSOCKET"
            self._state.last_connected_at = now
            self._state.last_error = None
        return self.status()

    def mark_disconnected(self, reason: str | None = None) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._state.connected = False
            self._state.mode = "REST_FALLBACK"
            self._state.last_disconnected_at = now
            self._state.reconnect_attempts += 1
            self._state.last_error = reason
        return self.status()

    def ingest_batch(self, ticks: list[dict[str, Any]], ingest: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(ticks, list):
            raise ValueError("ticks must be a list")
        overflow = max(0, len(ticks) - self.max_queue_size)
        working = ticks[: self.max_queue_size]
        now = datetime.now(timezone.utc).isoformat()
        accepted = ignored = rejected = 0
        results: list[dict[str, Any]] = []
        for start in range(0, len(working), self.max_batch_size):
            for tick in working[start:start + self.max_batch_size]:
                result = ingest(tick)
                results.append(result)
                status = result.get("status")
                if status == "ACCEPTED":
                    accepted += 1
                elif status == "IGNORED":
                    ignored += 1
                else:
                    rejected += 1
        summary = {
            "received": len(ticks), "processed": len(working), "accepted": accepted,
            "ignored": ignored, "rejected": rejected, "dropped": overflow,
            "processed_at": now, "live_orders_enabled": False,
        }
        with self._lock:
            self._state.received_batches += 1
            self._state.received_ticks += len(ticks)
            self._state.accepted_ticks += accepted
            self._state.ignored_ticks += ignored
            self._state.rejected_ticks += rejected
            self._state.dropped_ticks += overflow
            self._state.last_batch_at = now
            self._recent_batches.append(summary)
        return {**summary, "results": results}

    def status(self) -> dict[str, Any]:
        with self._lock:
            data = asdict(self._state)
            data.update({
                "subscription_count": len(self._state.subscribed_tokens),
                "max_batch_size": self.max_batch_size,
                "max_queue_size": self.max_queue_size,
                "execution_mode": "MARKET_DATA_ONLY",
                "live_orders_enabled": False,
            })
            return data

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._recent_batches)[-max(1, min(limit, 100)):][::-1]


_manager: KiteStreamManager | None = None


def get_stream_manager(requested: bool, max_batch_size: int, max_queue_size: int) -> KiteStreamManager:
    global _manager
    if _manager is None:
        _manager = KiteStreamManager(requested=requested, max_batch_size=max_batch_size, max_queue_size=max_queue_size)
    return _manager
