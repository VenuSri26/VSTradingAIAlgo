"""Restart-safe tick ingestion bridge for paper-trade monitoring.

The bridge accepts normalized broker ticks, rejects duplicates/out-of-order data,
and routes only matching option ticks into the existing paper lifecycle engine.
It never submits broker orders.
"""
from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from app.market_clock import parse_timestamp


@dataclass
class TickBridgeState:
    received: int = 0
    accepted: int = 0
    duplicates: int = 0
    out_of_order: int = 0
    invalid: int = 0
    routed_to_paper: int = 0
    last_tick_at: str | None = None
    last_exchange_timestamp: str | None = None
    last_symbol: str | None = None
    last_price: float | None = None
    last_action: str = "NOT_STARTED"
    last_error: str | None = None


class TickBridge:
    def __init__(self, history_path: str, max_history: int = 500):
        self.history_path = Path(history_path)
        self.max_history = max(10, max_history)
        self._lock = RLock()
        self._state = TickBridgeState()
        self._last_by_instrument: dict[str, tuple[datetime, str]] = {}
        self._recent: deque[dict[str, Any]] = deque(maxlen=self.max_history)
        self._load()

    def _load(self) -> None:
        if not self.history_path.exists():
            return
        try:
            lines = self.history_path.read_text(encoding="utf-8").splitlines()[-self.max_history:]
            for line in lines:
                row = json.loads(line)
                self._recent.append(row)
                key = str(row.get("instrument_key") or "")
                ts = parse_timestamp(row.get("exchange_timestamp"))
                fingerprint = str(row.get("fingerprint") or "")
                if key:
                    self._last_by_instrument[key] = (ts, fingerprint)
            if self._recent:
                row = self._recent[-1]
                self._state.last_tick_at = row.get("received_at")
                self._state.last_exchange_timestamp = row.get("exchange_timestamp")
                self._state.last_symbol = row.get("tradingsymbol")
                self._state.last_price = row.get("ltp")
                self._state.last_action = "RESTORED"
        except (OSError, ValueError, TypeError):
            self._state.last_error = "Tick history could not be restored"

    @staticmethod
    def _instrument_key(tick: dict[str, Any]) -> str:
        token = tick.get("instrument_token")
        symbol = tick.get("tradingsymbol")
        if token is not None:
            return str(token)
        if symbol:
            return str(symbol)
        option_type = str(tick.get("option_type") or "").upper()
        strike = tick.get("strike")
        return f"{option_type}:{strike}"

    @staticmethod
    def _matches_trade(tick: dict[str, Any], trade: dict[str, Any]) -> bool:
        return (
            str(tick.get("option_type") or "").upper() == str(trade.get("option_type") or "").upper()
            and int(float(tick.get("strike") or -1)) == int(trade.get("strike") or -2)
        )

    def ingest(
        self,
        tick: dict[str, Any],
        *,
        open_trade: dict[str, Any] | None = None,
        monitor: Callable[[dict[str, Any], float], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._state.received += 1
        try:
            ltp = float(tick.get("ltp"))
            if ltp <= 0:
                raise ValueError("ltp must be greater than zero")
            exchange_dt = parse_timestamp(tick.get("exchange_timestamp") or tick.get("timestamp"))
            exchange_utc = exchange_dt.astimezone(timezone.utc).isoformat()
            key = self._instrument_key(tick)
            if not key or key == ":None":
                raise ValueError("instrument identity is required")
            sequence = tick.get("sequence")
            fingerprint = f"{exchange_utc}|{ltp}|{sequence if sequence is not None else ''}"

            with self._lock:
                previous = self._last_by_instrument.get(key)
                if previous:
                    previous_dt, previous_fingerprint = previous
                    if fingerprint == previous_fingerprint:
                        self._state.duplicates += 1
                        self._state.last_action = "DUPLICATE_IGNORED"
                        return {"status": "IGNORED", "reason": "DUPLICATE_TICK", "paper_action": None}
                    if exchange_dt < previous_dt:
                        self._state.out_of_order += 1
                        self._state.last_action = "OUT_OF_ORDER_IGNORED"
                        return {"status": "IGNORED", "reason": "OUT_OF_ORDER_TICK", "paper_action": None}

                received_at = datetime.now(timezone.utc).isoformat()
                row = {
                    "instrument_key": key,
                    "instrument_token": tick.get("instrument_token"),
                    "tradingsymbol": tick.get("tradingsymbol"),
                    "option_type": str(tick.get("option_type") or "").upper() or None,
                    "strike": tick.get("strike"),
                    "ltp": ltp,
                    "exchange_timestamp": exchange_utc,
                    "received_at": received_at,
                    "sequence": sequence,
                    "fingerprint": fingerprint,
                }
                self._last_by_instrument[key] = (exchange_dt, fingerprint)
                self._recent.append(row)
                self._state.accepted += 1
                self._state.last_tick_at = received_at
                self._state.last_exchange_timestamp = exchange_utc
                self._state.last_symbol = row["tradingsymbol"] or key
                self._state.last_price = ltp
                self._state.last_error = None
                self.history_path.parent.mkdir(parents=True, exist_ok=True)
                with self.history_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")

            paper_result = None
            if open_trade and monitor and self._matches_trade(tick, open_trade):
                paper_result = monitor(open_trade, ltp)
                with self._lock:
                    self._state.routed_to_paper += 1
                    self._state.last_action = str(paper_result.get("action") or "PAPER_MONITORED")
            else:
                with self._lock:
                    self._state.last_action = "ACCEPTED_NO_MATCHING_PAPER_TRADE"

            return {
                "status": "ACCEPTED",
                "reason": None,
                "tick": row,
                "paper_action": paper_result,
                "live_orders_enabled": False,
            }
        except Exception as exc:
            with self._lock:
                self._state.invalid += 1
                self._state.last_action = "INVALID_TICK"
                self._state.last_error = str(exc)
            return {"status": "REJECTED", "reason": str(exc), "paper_action": None, "live_orders_enabled": False}

    def status(self) -> dict[str, Any]:
        with self._lock:
            state = asdict(self._state)
            state.update({
                "tracked_instruments": len(self._last_by_instrument),
                "history_size": len(self._recent),
                "execution_mode": "PAPER_TICK_MONITOR_ONLY",
                "live_orders_enabled": False,
            })
            return state

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._recent)[-max(1, min(limit, self.max_history)):][::-1]


_bridge: TickBridge | None = None


def get_tick_bridge(path: str) -> TickBridge:
    global _bridge
    if _bridge is None or str(_bridge.history_path) != str(Path(path)):
        _bridge = TickBridge(path)
    return _bridge
