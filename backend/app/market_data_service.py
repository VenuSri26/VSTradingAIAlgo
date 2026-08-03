from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable


@dataclass
class Candle:
    start: str
    end: str
    open: float
    high: float
    low: float
    close: float
    ticks: int


@dataclass
class MarketFeedState:
    running: bool = False
    mode: str = "SAFE_REST_POLLING"
    connected: bool = False
    authenticated: bool = False
    last_poll_at: str | None = None
    last_success_at: str | None = None
    last_market_timestamp: str | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    reconnects: int = 0
    polls: int = 0
    successful_polls: int = 0
    spot: float | None = None
    vix: float | None = None
    expiry: str | None = None
    instruments_synced: int = 0
    instrument_sync_at: str | None = None
    token_checked_at: str | None = None
    token_user_id: str | None = None
    websocket_requested: bool = False
    websocket_active: bool = False
    safe_no_trade: bool = True
    message: str = "Market feed has not started"
    candles_3m: list[dict[str, Any]] = field(default_factory=list)


class CandleAggregator:
    def __init__(self, timeframe_minutes: int = 3, max_candles: int = 120):
        self.timeframe_minutes = timeframe_minutes
        self._candles: deque[Candle] = deque(maxlen=max_candles)
        self._current: Candle | None = None

    def _bucket(self, timestamp: datetime) -> tuple[datetime, datetime]:
        timestamp = timestamp.astimezone(timezone.utc).replace(second=0, microsecond=0)
        minute = timestamp.minute - timestamp.minute % self.timeframe_minutes
        start = timestamp.replace(minute=minute)
        return start, start + timedelta(minutes=self.timeframe_minutes)

    def add(self, price: float, timestamp: datetime | None = None) -> None:
        timestamp = timestamp or datetime.now(timezone.utc)
        start, end = self._bucket(timestamp)
        if self._current is None or self._current.start != start.isoformat():
            if self._current is not None:
                self._candles.append(self._current)
            self._current = Candle(start.isoformat(), end.isoformat(), price, price, price, price, 1)
            return
        self._current.high = max(self._current.high, price)
        self._current.low = min(self._current.low, price)
        self._current.close = price
        self._current.ticks += 1

    def snapshot(self, include_current: bool = True) -> list[dict[str, Any]]:
        items = [asdict(item) for item in self._candles]
        if include_current and self._current is not None:
            items.append(asdict(self._current))
        return items


class MarketDataSupervisor:
    def __init__(self, state_path: str, poll_interval_sec: float, stale_after_sec: float, websocket_requested: bool):
        self.state_path = Path(state_path)
        self.poll_interval_sec = max(1.0, poll_interval_sec)
        self.stale_after_sec = max(1.0, stale_after_sec)
        self._state = MarketFeedState(websocket_requested=websocket_requested)
        self._lock = Lock()
        self._candles = CandleAggregator(3)
        self._stop = asyncio.Event()
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.state_path.read_text())
            allowed = {name for name in MarketFeedState.__dataclass_fields__}
            self._state = MarketFeedState(**{k: v for k, v in payload.items() if k in allowed})
            self._state.running = False
            self._state.websocket_active = False
        except (OSError, ValueError, TypeError):
            return

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(self._state), indent=2, sort_keys=True))
        temp.replace(self.state_path)

    def _update(self, **values: Any) -> None:
        with self._lock:
            for key, value in values.items():
                setattr(self._state, key, value)
            self._state.candles_3m = self._candles.snapshot()
            self._persist()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            payload = asdict(self._state)
        age = None
        reference = payload.get("last_market_timestamp") or payload.get("last_success_at")
        if reference:
            try:
                ts = datetime.fromisoformat(str(reference).replace("Z", "+00:00"))
                age = max(0.0, (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds())
            except ValueError:
                age = None
        payload["age_sec"] = round(age, 2) if age is not None else None
        payload["fresh"] = bool(payload["connected"] and age is not None and age <= self.stale_after_sec)
        payload["safe_no_trade"] = not payload["fresh"]
        payload["success_rate"] = round(payload["successful_polls"] / payload["polls"] * 100, 2) if payload["polls"] else None
        return payload

    def sync_instruments(self, data_source: Any) -> dict[str, Any]:
        started = datetime.now(timezone.utc).isoformat()
        if hasattr(data_source, "instrument_sync_status"):
            result = data_source.instrument_sync_status(force=True)
        else:
            chain = data_source.get_option_chain(atm_range=8)
            result = {
                "count": len(chain.get("chain", {}).get("CE", [])) + len(chain.get("chain", {}).get("PE", [])),
                "expiry": chain.get("expiry"),
                "source": getattr(data_source, "source_name", "UNKNOWN"),
            }
        self._update(
            instruments_synced=int(result.get("count") or 0),
            expiry=result.get("expiry"),
            instrument_sync_at=started,
            message="Instrument synchronization completed",
        )
        return {**result, "synced_at": started}

    def poll_once(self, data_source: Any) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._state.polls += 1
            self._state.last_poll_at = now.isoformat()
        try:
            token_health = data_source.token_health() if hasattr(data_source, "token_health") else {
                "connected": True, "source": getattr(data_source, "source_name", "UNKNOWN")
            }
            spot = float(data_source.get_spot())
            vix = float(data_source.get_vix())
            options = data_source.get_option_chain(atm_range=8)
            market_timestamp = now.isoformat()
            if hasattr(data_source, "get_last_tick_timestamp"):
                try:
                    market_timestamp = data_source.get_last_tick_timestamp()
                except Exception:
                    pass
            self._candles.add(spot, now)
            count = len(options.get("chain", {}).get("CE", [])) + len(options.get("chain", {}).get("PE", []))
            with self._lock:
                if self._state.consecutive_failures:
                    self._state.reconnects += 1
                self._state.successful_polls += 1
            self._update(
                running=True,
                connected=True,
                authenticated=bool(token_health.get("connected")),
                token_checked_at=token_health.get("checked_at") or now.isoformat(),
                token_user_id=token_health.get("user_id"),
                last_success_at=now.isoformat(),
                last_market_timestamp=market_timestamp,
                last_error=None,
                consecutive_failures=0,
                spot=spot,
                vix=vix,
                expiry=options.get("expiry"),
                instruments_synced=count,
                safe_no_trade=False,
                message="Live market snapshot refreshed",
            )
        except Exception as exc:
            with self._lock:
                failures = self._state.consecutive_failures + 1
            self._update(
                running=True,
                connected=False,
                authenticated=False,
                consecutive_failures=failures,
                last_error=str(exc)[:500],
                safe_no_trade=True,
                message="Market-data refresh failed; NO_TRADE safety state active",
            )
        return self.snapshot()

    async def run(self, get_data_source: Callable[[], Any]) -> None:
        self._stop.clear()
        self._update(running=True, message="Market-data supervisor started")
        try:
            while not self._stop.is_set():
                self.poll_once(get_data_source())
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval_sec)
                except asyncio.TimeoutError:
                    pass
        finally:
            self._update(running=False, websocket_active=False, message="Market-data supervisor stopped")

    def stop(self) -> None:
        self._stop.set()


_supervisor: MarketDataSupervisor | None = None


def get_supervisor(state_path: str, poll_interval_sec: float, stale_after_sec: float, websocket_requested: bool) -> MarketDataSupervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = MarketDataSupervisor(state_path, poll_interval_sec, stale_after_sec, websocket_requested)
    return _supervisor
