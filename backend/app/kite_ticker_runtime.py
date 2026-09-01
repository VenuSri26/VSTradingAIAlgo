"""Actual KiteTicker transport runtime with safe restart and reconnect controls.

The runtime only transports market data into the existing tick bridge. It never
submits broker orders. It is disabled unless TRADING_MODE=live and
KITE_WEBSOCKET_REQUESTED=true.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Callable

from app.config import settings
from app.kite_stream_manager import get_stream_manager


@dataclass
class RuntimeState:
    enabled: bool = False
    running: bool = False
    connected: bool = False
    transport: str = "REST_FALLBACK"
    started_at: str | None = None
    stopped_at: str | None = None
    last_callback_at: str | None = None
    last_tick_at: str | None = None
    last_error: str | None = None
    reconnect_attempts: int = 0
    reconnect_delay_sec: float = 0.0
    next_reconnect_at: str | None = None
    subscriptions_synced_at: str | None = None
    metadata_count: int = 0
    market_open: bool = True
    market_session: str = "UNKNOWN"


class KiteTickerRuntime:
    def __init__(self, *, heartbeat_timeout_sec: float, reconnect_base_sec: float, reconnect_max_sec: float):
        self.heartbeat_timeout_sec = max(5.0, heartbeat_timeout_sec)
        self.reconnect_base_sec = max(1.0, reconnect_base_sec)
        self.reconnect_max_sec = max(self.reconnect_base_sec, reconnect_max_sec)
        self._lock = RLock()
        self._state = RuntimeState(enabled=settings.is_live() and settings.kite_websocket_requested)
        self._ticker: Any | None = None
        self._metadata: dict[int, dict[str, Any]] = {}
        self._factory: Callable[[str, str], Any] | None = None
        self._ingest: Callable[[dict[str, Any]], dict[str, Any]] | None = None


    def set_market_session(self, market_open: bool, session: str) -> None:
        with self._lock:
            self._state.market_open = bool(market_open)
            self._state.market_session = str(session)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def configure_contracts(self, contracts: list[dict[str, Any]]) -> dict[str, Any]:
        metadata: dict[int, dict[str, Any]] = {}
        for item in contracts:
            token = int(item.get("instrument_token") or 0)
            if token <= 0:
                continue
            metadata[token] = {
                "instrument_token": token,
                "tradingsymbol": item.get("tradingsymbol"),
                "option_type": item.get("option_type"),
                "strike": item.get("strike"),
                "expiry": item.get("expiry"),
                "asset_type": item.get("asset_type"),
            }
        with self._lock:
            self._metadata = metadata
            self._state.metadata_count = len(metadata)
            self._state.subscriptions_synced_at = self._now().isoformat()
        manager = get_stream_manager(settings.kite_websocket_requested, settings.websocket_batch_size, settings.websocket_queue_size)
        manager.subscribe(list(metadata))
        self._subscribe_connected()
        return self.status()

    def start(self, *, factory: Callable[[str, str], Any] | None = None,
              ingest: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
        with self._lock:
            if self._state.running:
                return self.status()
            self._state.enabled = settings.is_live() and settings.kite_websocket_requested
            if not self._state.enabled:
                self._state.transport = "REST_FALLBACK"
                self._state.last_error = "KiteTicker runtime is disabled by configuration"
                return self.status()
            if not settings.kite_api_key or not settings.kite_access_token:
                self._state.last_error = "Kite API key/access token missing"
                self._state.transport = "REST_FALLBACK"
                return self.status()
            self._factory = factory or self._default_factory
            self._ingest = ingest or self._default_ingest
            self._state.running = True
            self._state.started_at = self._now().isoformat()
            self._state.stopped_at = None
        self._connect()
        return self.status()

    def stop(self, reason: str = "runtime stopped") -> dict[str, Any]:
        ticker = None
        with self._lock:
            ticker, self._ticker = self._ticker, None
            self._state.running = False
            self._state.connected = False
            self._state.transport = "REST_FALLBACK"
            self._state.stopped_at = self._now().isoformat()
            self._state.last_error = reason
            self._state.next_reconnect_at = None
        if ticker is not None:
            try:
                ticker.close()
            except Exception:
                pass
        get_stream_manager(settings.kite_websocket_requested, settings.websocket_batch_size, settings.websocket_queue_size).mark_disconnected(reason)
        return self.status()

    def _default_factory(self, api_key: str, access_token: str):
        from kiteconnect import KiteTicker
        return KiteTicker(api_key, access_token, reconnect=False)

    @staticmethod
    def _default_ingest(tick: dict[str, Any]) -> dict[str, Any]:
        from app import store
        from app.live_market_stream import get_live_market_stream
        from app.paper_trade_management import evaluate
        from app.tick_bridge import get_tick_bridge

        stream_result = get_live_market_stream().ingest(tick)
        # Index/VIX ticks belong in the live market cache but must never be
        # routed into option paper-trade monitoring.
        if str(tick.get("option_type") or "").upper() not in {"CE", "PE"}:
            return stream_result

        def monitor(trade: dict, price: float):
            result = evaluate(trade, price)
            detail = ",".join(result.get("actions") or []) or result.get("reason")
            store.record_paper_monitor_event(trade["id"], price, result["action"], detail)
            if result["action"] == "CLOSED" and result.get("net_pnl") is not None:
                store.record_trade_result(result["net_pnl"], "B")
            return result

        return get_tick_bridge(settings.tick_bridge_history_path).ingest(
            tick, open_trade=store.get_open_paper_trade(), monitor=monitor
        )

    def _connect(self) -> None:
        with self._lock:
            if not self._state.running or self._ticker is not None:
                return
            factory = self._factory
        try:
            ticker = factory(settings.kite_api_key or "", settings.kite_access_token or "")
            ticker.on_connect = self._on_connect
            ticker.on_ticks = self._on_ticks
            ticker.on_close = self._on_close
            ticker.on_error = self._on_error
            ticker.on_reconnect = self._on_reconnect
            ticker.on_noreconnect = self._on_noreconnect
            with self._lock:
                self._ticker = ticker
                self._state.transport = "WEBSOCKET_CONNECTING"
                self._state.last_error = None
            ticker.connect(threaded=True)
        except Exception as exc:
            with self._lock:
                self._ticker = None
            self._schedule_reconnect(f"connect failed: {exc}")

    def _on_connect(self, ws, response) -> None:
        now = self._now().isoformat()
        with self._lock:
            self._state.connected = True
            self._state.transport = "WEBSOCKET"
            self._state.last_callback_at = now
            self._state.last_error = None
            self._state.reconnect_delay_sec = 0.0
            self._state.next_reconnect_at = None
        get_stream_manager(settings.kite_websocket_requested, settings.websocket_batch_size, settings.websocket_queue_size).mark_connected()
        self._subscribe_connected(ws)

    def _subscribe_connected(self, ws=None) -> None:
        with self._lock:
            ticker = ws or self._ticker
            tokens = sorted(self._metadata)
            connected = self._state.connected
        if not ticker or not connected or not tokens:
            return
        try:
            ticker.subscribe(tokens)
            if hasattr(ticker, "set_mode") and hasattr(ticker, "MODE_FULL"):
                ticker.set_mode(ticker.MODE_FULL, tokens)
        except Exception as exc:
            with self._lock:
                self._state.last_error = f"subscription failed: {exc}"

    @staticmethod
    def _iso(value: Any) -> str:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if value:
            return str(value)
        return datetime.now(timezone.utc).isoformat()

    def _normalize_tick(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        token = int(raw.get("instrument_token") or 0)
        with self._lock:
            meta = dict(self._metadata.get(token) or {})
        if token <= 0 or not meta:
            return None
        return {
            **meta,
            "ltp": raw.get("last_price"),
            "volume": raw.get("volume_traded"),
            "oi": raw.get("oi"),
            "exchange_timestamp": self._iso(raw.get("exchange_timestamp") or raw.get("last_trade_time")),
            "sequence": raw.get("sequence") or raw.get("timestamp") or 0,
        }

    def _on_ticks(self, ws, ticks) -> None:
        now = self._now().isoformat()
        normalized = [item for item in (self._normalize_tick(raw) for raw in (ticks or [])) if item]
        with self._lock:
            self._state.last_callback_at = now
            if normalized:
                self._state.last_tick_at = now
        if normalized and self._ingest:
            get_stream_manager(settings.kite_websocket_requested, settings.websocket_batch_size, settings.websocket_queue_size).ingest_batch(normalized, self._ingest)

    def _on_close(self, ws, code, reason) -> None:
        with self._lock:
            self._ticker = None
            should_reconnect = self._state.running
        if should_reconnect:
            self._schedule_reconnect(f"socket closed {code}: {reason}")

    def _on_error(self, ws, code, reason) -> None:
        with self._lock:
            self._state.last_callback_at = self._now().isoformat()
            self._state.last_error = f"socket error {code}: {reason}"

    def _on_reconnect(self, ws, attempts_count) -> None:
        with self._lock:
            self._state.reconnect_attempts = max(self._state.reconnect_attempts, int(attempts_count or 0))

    def _on_noreconnect(self, ws) -> None:
        self._schedule_reconnect("broker SDK stopped reconnecting")

    def _schedule_reconnect(self, reason: str) -> None:
        now = self._now()
        with self._lock:
            self._state.connected = False
            self._state.transport = "REST_FALLBACK"
            self._state.last_error = reason[:500]
            self._state.reconnect_attempts += 1
            delay = min(self.reconnect_max_sec, self.reconnect_base_sec * (2 ** max(0, self._state.reconnect_attempts - 1)))
            self._state.reconnect_delay_sec = delay
            self._state.next_reconnect_at = (now + timedelta(seconds=delay)).isoformat()
        get_stream_manager(settings.kite_websocket_requested, settings.websocket_batch_size, settings.websocket_queue_size).mark_disconnected(reason)

    def monitor_once(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or self._now()
        reconnect = False
        close_ticker = None
        with self._lock:
            if not self._state.running:
                return self.status()
            if self._state.market_open and self._state.connected and self._state.last_callback_at and self._metadata:
                last = datetime.fromisoformat(self._state.last_callback_at.replace("Z", "+00:00"))
                if (now - last.astimezone(timezone.utc)).total_seconds() > self.heartbeat_timeout_sec:
                    close_ticker = self._ticker
                    self._ticker = None
                    self._schedule_reconnect("heartbeat timeout")
            if not self._state.connected and self._state.next_reconnect_at:
                due = datetime.fromisoformat(self._state.next_reconnect_at.replace("Z", "+00:00"))
                reconnect = now >= due.astimezone(timezone.utc)
                if reconnect:
                    self._state.next_reconnect_at = None
        if close_ticker is not None:
            try:
                close_ticker.close()
            except Exception:
                pass
        if reconnect:
            self._connect()
        return self.status()

    async def monitor_loop(self) -> None:
        while True:
            self.monitor_once()
            await asyncio.sleep(max(1.0, min(5.0, self.heartbeat_timeout_sec / 3)))

    def status(self) -> dict[str, Any]:
        now = self._now()
        with self._lock:
            payload = asdict(self._state)
        age = None
        if payload.get("last_callback_at"):
            last = datetime.fromisoformat(payload["last_callback_at"].replace("Z", "+00:00"))
            age = max(0.0, (now - last.astimezone(timezone.utc)).total_seconds())
        payload.update({
            "heartbeat_age_sec": round(age, 2) if age is not None else None,
            "heartbeat_timeout_sec": self.heartbeat_timeout_sec,
            "subscription_count": payload["metadata_count"],
            "execution_mode": "MARKET_DATA_ONLY",
            "live_orders_enabled": False,
        })
        return payload


_runtime: KiteTickerRuntime | None = None


def get_kite_ticker_runtime() -> KiteTickerRuntime:
    global _runtime
    if _runtime is None:
        _runtime = KiteTickerRuntime(
            heartbeat_timeout_sec=settings.websocket_heartbeat_timeout_sec,
            reconnect_base_sec=settings.websocket_reconnect_base_sec,
            reconnect_max_sec=settings.websocket_reconnect_max_sec,
        )
    return _runtime
