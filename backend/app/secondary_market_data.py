"""Provider-neutral secondary quote adapter used for shadow consensus."""
from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from app.market_data_consensus import MarketDataEnvelopeV2


class SecondaryQuoteAdapter(Protocol):
    def latest(self, instrument: str) -> MarketDataEnvelopeV2 | None: ...


class ReplaySecondaryQuoteAdapter:
    """Durable JSONL adapter with no broker-order capability."""

    def __init__(self, path: str, max_history: int = 1000):
        self.path = Path(path)
        self.max_history = max(10, max_history)
        self._lock = RLock()
        self._latest: dict[str, MarketDataEnvelopeV2] = {}
        self._load()

    @staticmethod
    def _from_raw(raw: dict[str, Any]) -> MarketDataEnvelopeV2:
        return MarketDataEnvelopeV2.create(**{
            key: raw.get(key) for key in (
                "source", "instrument", "last_price", "exchange_timestamp",
                "received_at", "instrument_token", "bid", "ask", "sequence",
                "provider_instrument_id",
            )
        })

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines()[-self.max_history:]:
                envelope = self._from_raw(json.loads(line))
                self._latest[envelope.instrument] = envelope
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._latest.clear()

    def ingest(self, raw: dict[str, Any]) -> MarketDataEnvelopeV2:
        envelope = self._from_raw(raw)
        with self._lock:
            previous = self._latest.get(envelope.instrument)
            if previous and previous.exchange_timestamp >= envelope.exchange_timestamp:
                raise ValueError("secondary quote must have a newer exchange timestamp")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(envelope.to_dict(), sort_keys=True) + "\n")
            self._latest[envelope.instrument] = envelope
        return envelope

    def latest(self, instrument: str) -> MarketDataEnvelopeV2 | None:
        with self._lock:
            return self._latest.get(str(instrument).strip().upper())

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "adapter": "REPLAY_JSONL",
                "configured": True,
                "path": str(self.path),
                "tracked_instruments": sorted(self._latest),
                "write_capability": "MARKET_DATA_ONLY",
                "broker_order_capability": False,
            }


_adapter: ReplaySecondaryQuoteAdapter | None = None


def get_secondary_quote_adapter(path: str) -> ReplaySecondaryQuoteAdapter:
    global _adapter
    if _adapter is None or str(_adapter.path) != str(Path(path)):
        _adapter = ReplaySecondaryQuoteAdapter(path)
    return _adapter
