"""Read-only Upstox V3 secondary quote adapter.

The adapter deliberately exposes no order methods. Provider failures are
reported through status and return no quote, allowing the primary feed to
continue while consensus remains degraded rather than fabricating evidence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Callable

import httpx

from app.market_data_consensus import MarketDataEnvelopeV2

UPSTOX_FULL_QUOTE_URL = "https://api.upstox.com/v3/market-quote/quotes"


class UpstoxV3QuoteAdapter:
    def __init__(
        self,
        access_token: str | None,
        instrument_key: str = "NSE_INDEX|Nifty 50",
        timeout_sec: float = 3.0,
        poll_interval_sec: float = 3.0,
        fetcher: Callable[..., Any] | None = None,
    ):
        self.access_token = access_token
        self.instrument_key = instrument_key
        self.timeout_sec = max(1.0, min(float(timeout_sec), 30.0))
        self.poll_interval_sec = max(1.0, float(poll_interval_sec))
        self._fetcher = fetcher or httpx.get
        self._lock = RLock()
        self._cached: MarketDataEnvelopeV2 | None = None
        self._last_attempt_at: datetime | None = None
        self._last_success_at: datetime | None = None
        self._last_error: str | None = None
        self._requests = 0
        self._successes = 0

    @staticmethod
    def _millis_to_datetime(value: Any) -> datetime:
        if value is None:
            raise ValueError("Upstox last_trade_time is missing or invalid")
        milliseconds = int(value)
        if milliseconds <= 0:
            raise ValueError("Upstox last_trade_time is missing or invalid")
        return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)

    def _parse(self, payload: dict[str, Any], received_at: datetime) -> MarketDataEnvelopeV2:
        if str(payload.get("status", "")).lower() != "success":
            raise ValueError("Upstox quote response status is not success")
        data = payload.get("data")
        if not isinstance(data, dict) or not data:
            raise ValueError("Upstox quote response contains no data")
        quote = next((v for v in data.values() if isinstance(v, dict)), None)
        if quote is None:
            raise ValueError("Upstox quote payload is malformed")
        provider_id = str(quote.get("instrument_token") or self.instrument_key)
        return MarketDataEnvelopeV2.create(
            source="UPSTOX_V3",
            instrument="NIFTY 50",
            provider_instrument_id=provider_id,
            last_price=quote.get("last_price"),
            exchange_timestamp=self._millis_to_datetime(quote.get("last_trade_time")),
            received_at=received_at,
        )

    def latest(self, instrument: str) -> MarketDataEnvelopeV2 | None:
        if str(instrument).strip().upper() != "NIFTY 50":
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            if self._last_attempt_at and now - self._last_attempt_at < timedelta(seconds=self.poll_interval_sec):
                return self._cached
            self._last_attempt_at = now
            self._requests += 1
        if not self.access_token:
            with self._lock:
                self._last_error = "UPSTOX_ACCESS_TOKEN_NOT_CONFIGURED"
            return None
        try:
            response = self._fetcher(
                UPSTOX_FULL_QUOTE_URL,
                params={"instrument_key": self.instrument_key},
                headers={"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"},
                timeout=self.timeout_sec,
            )
            response.raise_for_status()
            envelope = self._parse(response.json(), datetime.now(timezone.utc))
            with self._lock:
                self._cached = envelope
                self._last_success_at = datetime.now(timezone.utc)
                self._last_error = None
                self._successes += 1
            return envelope
        except Exception as exc:
            with self._lock:
                self._last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
                return self._cached

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "adapter": "UPSTOX_V3_FULL_QUOTE",
                "enabled": bool(self.access_token),
                "instrument_key": self.instrument_key,
                "endpoint": UPSTOX_FULL_QUOTE_URL,
                "last_attempt_at": self._last_attempt_at.isoformat() if self._last_attempt_at else None,
                "last_success_at": self._last_success_at.isoformat() if self._last_success_at else None,
                "last_error": self._last_error,
                "requests": self._requests,
                "successes": self._successes,
                "write_capability": "MARKET_DATA_ONLY",
                "broker_order_capability": False,
            }


_adapter: UpstoxV3QuoteAdapter | None = None


def get_upstox_quote_adapter(
    access_token: str | None,
    instrument_key: str,
    timeout_sec: float,
    poll_interval_sec: float,
) -> UpstoxV3QuoteAdapter:
    global _adapter
    identity = (access_token, instrument_key, float(timeout_sec), float(poll_interval_sec))
    current = None if _adapter is None else (
        _adapter.access_token, _adapter.instrument_key, _adapter.timeout_sec, _adapter.poll_interval_sec,
    )
    if _adapter is None or current != identity:
        _adapter = UpstoxV3QuoteAdapter(*identity)
    return _adapter
