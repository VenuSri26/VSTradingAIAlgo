"""Deterministic fail-closed market-data quality gate for live execution."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from math import isfinite
from typing import Any

from app.config import settings


@dataclass(frozen=True)
class DataQualityDecision:
    approved: bool
    blockers: list[str]
    warnings: list[str]
    checks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_age(value: str | None) -> float | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return max(0.0, (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


def _parse_expiry(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def evaluate_runtime_quality(
    market_snapshot: dict[str, Any],
    runtime_snapshot: dict[str, Any] | None,
    *,
    max_age_sec: float,
    websocket_required: bool,
) -> DataQualityDecision:
    blockers: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    age = market_snapshot.get("age_sec")
    fresh = bool(market_snapshot.get("fresh")) and age is not None and float(age) <= max_age_sec
    checks.append({"name": "market_snapshot_fresh", "passed": fresh, "detail": f"age_sec={age}"})
    if not fresh:
        blockers.append("STALE_MARKET_DATA")

    authenticated = bool(market_snapshot.get("authenticated"))
    checks.append({"name": "broker_authenticated", "passed": authenticated, "detail": str(authenticated)})
    if not authenticated:
        blockers.append("BROKER_NOT_AUTHENTICATED")

    instruments = int(market_snapshot.get("instruments_synced") or 0)
    checks.append({"name": "instrument_master_ready", "passed": instruments > 0, "detail": f"count={instruments}"})
    if instruments <= 0:
        blockers.append("INSTRUMENT_MASTER_NOT_READY")

    expiry = market_snapshot.get("expiry")
    checks.append({"name": "expiry_resolved", "passed": bool(expiry), "detail": f"expiry={expiry}"})
    if not expiry:
        blockers.append("EXPIRY_UNRESOLVED")

    if websocket_required:
        runtime_snapshot = runtime_snapshot or {}
        connected = bool(runtime_snapshot.get("connected")) and runtime_snapshot.get("transport") == "WEBSOCKET"
        tick_age = _parse_age(runtime_snapshot.get("last_tick_at"))
        tick_fresh = connected and tick_age is not None and tick_age <= max_age_sec
        checks.append({"name": "kite_websocket_connected", "passed": connected, "detail": str(runtime_snapshot.get("transport"))})
        checks.append({"name": "kite_tick_fresh", "passed": tick_fresh, "detail": f"tick_age_sec={tick_age}"})
        if not connected:
            blockers.append("KITE_WEBSOCKET_NOT_HEALTHY")
        if not tick_fresh:
            blockers.append("KITE_TICK_STALE")
        if runtime_snapshot.get("next_reconnect_at"):
            blockers.append("KITE_RECONNECTING")
    else:
        warnings.append("WEBSOCKET_NOT_REQUIRED_BY_CONFIGURATION")

    consensus = market_snapshot.get("source_consensus") or {}
    consensus_status = str(consensus.get("status") or "UNAVAILABLE")
    consensus_verified = bool(consensus.get("approved")) and consensus_status == "VERIFIED"
    checks.append({"name": "source_consensus_verified", "passed": consensus_verified, "detail": consensus_status})
    if settings.market_data_consensus_required and not consensus_verified:
        blockers.append(f"SOURCE_CONSENSUS_{consensus_status}")
    elif not consensus_verified:
        warnings.append(f"SOURCE_CONSENSUS_{consensus_status}")

    return DataQualityDecision(not blockers, blockers, warnings, checks)


def current_live_data_quality() -> DataQualityDecision:
    from app.market_data_service import get_supervisor

    supervisor = get_supervisor(
        settings.market_data_state_path,
        settings.market_data_poll_interval_sec,
        settings.max_data_age_sec,
        settings.kite_websocket_requested,
    )
    market = supervisor.snapshot()
    runtime = None
    if settings.kite_websocket_requested:
        from app.kite_ticker_runtime import get_kite_ticker_runtime
        runtime = get_kite_ticker_runtime().status()
    return evaluate_runtime_quality(
        market,
        runtime,
        max_age_sec=float(settings.max_data_age_sec),
        websocket_required=bool(settings.kite_websocket_requested),
    )


def evaluate_order_quote(order: dict[str, Any], option_snapshot: dict[str, Any], *, max_spread_pct: float = 3.0) -> DataQualityDecision:
    blockers: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []
    symbol = str(order.get("tradingsymbol") or "").upper().replace("NFO:", "")
    matches: list[tuple[str, dict[str, Any]]] = []
    for side in ("CE", "PE"):
        for item in (option_snapshot.get("chain", {}) or {}).get(side, []) or []:
            if str(item.get("tradingsymbol") or "").upper() == symbol:
                matches.append((side, item))
    unique = len(matches) == 1
    checks.append({"name": "contract_unique_in_live_chain", "passed": unique, "detail": f"{symbol}; matches={len(matches)}"})
    if not matches:
        blockers.append("CONTRACT_NOT_IN_LIVE_CHAIN")
        return DataQualityDecision(False, blockers, warnings, checks)
    if not unique:
        blockers.append("AMBIGUOUS_CONTRACT_IDENTITY")
        return DataQualityDecision(False, blockers, warnings, checks)

    chain_side, leg = matches[0]
    snapshot_expiry = _parse_expiry(option_snapshot.get("expiry"))
    leg_expiry = _parse_expiry(leg.get("expiry"))
    expiry_ok = (
        snapshot_expiry is not None
        and leg_expiry is not None
        and snapshot_expiry == leg_expiry
        and snapshot_expiry >= datetime.now(timezone.utc).date()
    )
    checks.append({
        "name": "active_expiry_matches_snapshot",
        "passed": expiry_ok,
        "detail": f"snapshot={snapshot_expiry}, contract={leg_expiry}",
    })
    if not expiry_ok:
        blockers.append("CONTRACT_EXPIRY_INVALID")

    exchange = str(leg.get("exchange") or "").upper()
    segment = str(leg.get("segment") or "").upper()
    venue_ok = exchange == "NFO" and segment == "NFO-OPT"
    checks.append({"name": "nfo_option_venue", "passed": venue_ok, "detail": f"exchange={exchange}, segment={segment}"})
    if not venue_ok:
        blockers.append("CONTRACT_VENUE_MISMATCH")

    option_type = str(leg.get("option_type") or "").upper()
    type_ok = option_type == chain_side and symbol.endswith(chain_side)
    checks.append({"name": "option_type_consistent", "passed": type_ok, "detail": f"chain={chain_side}, contract={option_type}"})
    if not type_ok:
        blockers.append("CONTRACT_OPTION_TYPE_MISMATCH")

    try:
        instrument_token = int(leg.get("instrument_token") or 0)
    except (TypeError, ValueError):
        instrument_token = 0
    token_ok = instrument_token > 0
    supplied_token = order.get("instrument_token")
    if supplied_token is not None:
        try:
            token_ok = token_ok and int(supplied_token) == instrument_token
        except (TypeError, ValueError):
            token_ok = False
    checks.append({"name": "instrument_token_verified", "passed": token_ok, "detail": f"token={instrument_token}"})
    if not token_ok:
        blockers.append("CONTRACT_TOKEN_MISMATCH")

    try:
        strike = float(leg.get("strike"))
    except (TypeError, ValueError):
        strike = 0.0
    strike_ok = isfinite(strike) and strike > 0
    supplied_strike = order.get("strike")
    if supplied_strike is not None:
        try:
            strike_ok = strike_ok and float(supplied_strike) == strike
        except (TypeError, ValueError):
            strike_ok = False
    checks.append({"name": "strike_verified", "passed": strike_ok, "detail": f"strike={strike}"})
    if not strike_ok:
        blockers.append("CONTRACT_STRIKE_MISMATCH")

    try:
        tick_size = float(leg.get("tick_size") or 0)
    except (TypeError, ValueError):
        tick_size = 0.0
    tick_ok = isfinite(tick_size) and tick_size > 0
    checks.append({"name": "tick_size_verified", "passed": tick_ok, "detail": f"tick_size={tick_size}"})
    if not tick_ok:
        blockers.append("CONTRACT_TICK_SIZE_INVALID")

    bid = float(leg.get("bid") or 0)
    ask = float(leg.get("ask") or 0)
    quote_ok = bid > 0 and ask > 0 and ask >= bid
    checks.append({"name": "bid_ask_available", "passed": quote_ok, "detail": f"bid={bid}, ask={ask}"})
    if not quote_ok:
        blockers.append("BID_ASK_UNAVAILABLE")
    spread_pct = ((ask - bid) / ((ask + bid) / 2) * 100) if quote_ok and (ask + bid) > 0 else None
    spread_ok = spread_pct is not None and spread_pct <= max_spread_pct
    checks.append({"name": "spread_within_limit", "passed": spread_ok, "detail": f"spread_pct={spread_pct}"})
    if not spread_ok:
        blockers.append("SPREAD_TOO_WIDE")

    live_lot_size = int(leg.get("lot_size") or 0)
    quantity = int(order.get("quantity") or 0)
    lot_ok = live_lot_size > 0 and quantity > 0 and quantity % live_lot_size == 0
    checks.append({
        "name": "live_contract_lot_multiple",
        "passed": lot_ok,
        "detail": f"quantity={quantity}, lot_size={live_lot_size}",
    })
    if not lot_ok:
        blockers.append("INVALID_LIVE_LOT_SIZE")

    volume = int(leg.get("volume") or 0)
    checks.append({"name": "option_has_volume", "passed": volume > 0, "detail": f"volume={volume}"})
    if volume <= 0:
        blockers.append("INSUFFICIENT_LIQUIDITY")

    quote_age = _parse_age(leg.get("quote_timestamp"))
    if quote_age is None:
        checks.append({"name": "option_quote_fresh", "passed": False, "detail": "timestamp unavailable"})
        blockers.append("OPTION_QUOTE_TIMESTAMP_UNAVAILABLE")
    else:
        quote_fresh = quote_age <= float(settings.max_data_age_sec)
        checks.append({"name": "option_quote_fresh", "passed": quote_fresh, "detail": f"age_sec={quote_age}"})
        if not quote_fresh:
            blockers.append("OPTION_QUOTE_STALE")

    return DataQualityDecision(not blockers, blockers, warnings, checks)
