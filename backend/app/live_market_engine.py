from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.config import settings
from app.features import build_features
from app.option_chain_intelligence import analyse_option_chain


class LiveMarketEngine:
    """Build a strict, source-aware market snapshot.

    In live mode this service never substitutes mock values. Any unavailable
    broker value is returned as unavailable with a blocker explaining why.
    """

    def __init__(self, data_source: Any, runtime: Any, supervisor: Any):
        self.data_source = data_source
        self.runtime = runtime
        self.supervisor = supervisor

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _source_name(self) -> str:
        return str(getattr(self.data_source, "source_name", "UNKNOWN")).upper()

    def _strict_live_blockers(self) -> list[str]:
        blockers: list[str] = []
        if not settings.is_live():
            blockers.append("TRADING_MODE_NOT_LIVE")
        if self._source_name() != "ZERODHA":
            blockers.append("ZERODHA_SOURCE_NOT_ACTIVE")
        return blockers

    def status(self) -> dict[str, Any]:
        runtime = self.runtime.status()
        feed = self.supervisor.snapshot()
        blockers = self._strict_live_blockers()
        warnings: list[str] = []

        if settings.is_live() and not runtime.get("enabled"):
            blockers.append("KITE_RUNTIME_DISABLED")
        if settings.is_live() and runtime.get("enabled") and not runtime.get("connected"):
            warnings.append("WEBSOCKET_NOT_CONNECTED_REST_FALLBACK_ACTIVE")
        if settings.is_live() and not feed.get("authenticated"):
            blockers.append("ZERODHA_AUTHENTICATION_INVALID")
        if settings.is_live() and feed.get("age_sec") is not None and not feed.get("fresh"):
            blockers.append("MARKET_DATA_STALE")
        if settings.is_live() and not feed.get("connected"):
            blockers.append("MARKET_FEED_DISCONNECTED")

        blockers = sorted(set(blockers))
        warnings = sorted(set(warnings))
        ready = not blockers and bool(feed.get("fresh"))
        return {
            "status": "READY" if ready else "BLOCKED",
            "ready_for_live_data": ready,
            "mode": settings.trading_mode,
            "source": self._source_name(),
            "transport": runtime.get("transport") or "REST_FALLBACK",
            "authenticated": bool(feed.get("authenticated")),
            "websocket_connected": bool(runtime.get("connected")),
            "subscription_count": int(runtime.get("subscription_count") or 0),
            "last_tick_at": runtime.get("last_tick_at"),
            "feed_age_sec": feed.get("age_sec"),
            "feed_fresh": bool(feed.get("fresh")),
            "blockers": blockers,
            "warnings": warnings,
            "live_orders_enabled": False,
            "generated_at": self._utc_now(),
        }

    def sources(self) -> dict[str, Any]:
        live = settings.is_live() and self._source_name() == "ZERODHA"
        direct = "ZERODHA" if live else "MOCK"
        derived = "DERIVED_FROM_LIVE_ZERODHA" if live else "DERIVED_FROM_MOCK"
        return {
            "mode": settings.trading_mode,
            "market_fields": {
                "nifty_spot": direct,
                "india_vix": direct,
                "option_ltp": direct,
                "option_bid_ask": direct,
                "option_oi": direct,
                "option_volume": direct,
                "pcr": derived,
                "max_pain": derived,
                "call_put_walls": derived,
                "technical_indicators": derived,
                "market_regime": derived,
                "greeks": "MODEL_DERIVED" if live else "MODEL_DERIVED_FROM_MOCK",
            },
            "policy": "NO_SYNTHETIC_FALLBACK_IN_LIVE_MODE",
            "live_orders_enabled": False,
        }

    def snapshot(self, atm_range: int = 8, candle_lookback: int = 120) -> dict[str, Any]:
        status = self.status()
        if settings.is_live() and status["blockers"]:
            return {
                **status,
                "market": None,
                "option_chain": None,
                "indicators": None,
                "recommended_action": "NO_TRADE",
            }

        try:
            spot = float(self.data_source.get_spot())
            vix = float(self.data_source.get_vix())
            chain = self.data_source.get_option_chain(atm_range=atm_range)
            option_summary = analyse_option_chain(chain)
            indicators: dict[str, Any] | None = None
            indicator_warnings: list[str] = []
            try:
                intraday = self.data_source.get_ohlc("3m", candle_lookback)
                daily = self.data_source.get_ohlc("1d", 5)
                if isinstance(intraday, pd.DataFrame) and isinstance(daily, pd.DataFrame) and len(intraday) >= 20 and len(daily) >= 1:
                    indicators = asdict(build_features(intraday, daily))
                else:
                    indicator_warnings.append("INSUFFICIENT_COMPLETED_CANDLES")
            except Exception as exc:
                indicator_warnings.append(f"INDICATORS_UNAVAILABLE: {exc}")

            result = {
                **status,
                "market": {
                    "spot": spot,
                    "india_vix": vix,
                    "atm_strike": chain.get("atm"),
                    "expiry": chain.get("expiry"),
                    "market_timestamp": getattr(self.data_source, "get_last_tick_timestamp", lambda: None)(),
                },
                "option_chain": {
                    "summary": option_summary,
                    "contracts": chain.get("chain", {}),
                },
                "indicators": indicators,
                "warnings": sorted(set(status["warnings"] + indicator_warnings)),
                "recommended_action": "USE_FOR_DECISION_SUPPORT" if status["ready_for_live_data"] else "PAPER_TEST_ONLY",
            }
            return result
        except Exception as exc:
            return {
                **status,
                "status": "BLOCKED",
                "ready_for_live_data": False,
                "market": None,
                "option_chain": None,
                "indicators": None,
                "blockers": sorted(set(status["blockers"] + [f"LIVE_SNAPSHOT_FAILED: {exc}"])),
                "recommended_action": "NO_TRADE",
            }
