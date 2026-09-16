from __future__ import annotations
from datetime import datetime, timezone, time
from zoneinfo import ZoneInfo

from app.config import settings
from app.data_sources.base import DataSource, DataUnavailable
from app.features import build_features, Features
from app.futures_volume import (
    build_futures_volume_snapshot,
    load_nifty_futures_ohlc,
    merge_futures_volume_into_features,
)
from app.models import (
    AgentResult, Decision, DecisionType, TradeGrade, TradePlan, EntryChecklistItem,
    RiskResult, PositionInfo, SystemHealth, ComponentHealth, HealthStatus,
    LiveDecisionResponse, Direction, Source, Availability, utcnow,
)
from app.agents.technical_agents import trend_agent, momentum_agent, regime_agent
from app.agents.htf_bias import htf_bias_agent, TIMEFRAMES
from app.agents.liquidity import liquidity_agent, trap_detection_agent, build_flags
from app.agents.options_agents import options_oi_agent, gamma_agent
from app.agents.risk import risk_agent
from app.agents.alignment import compute_alignment, classify_trade_grade
from app.agents.debate import build_debate
from app.agents.market_structure import analyse_market_structure
from app.agents.narrative import build_narrative
from app import store, greeks as greeks_module
from app.decision_evidence import build_decision_evidence


def _days_to_expiry(expiry_str: str | None, now: datetime) -> float | None:
    if not expiry_str:
        return None
    try:
        from datetime import date
        expiry_date = date.fromisoformat(expiry_str[:10])
        # NSE options expire at end of trading day (~15:30 IST); treat
        # expiry day itself as a fraction of a day remaining rather than 0,
        # so Greeks near expiry don't blow up to a divide-by-zero.
        delta_days = (expiry_date - now.date()).days
        return max(delta_days, 0) + 0.25
    except (ValueError, TypeError):
        return None


IST = ZoneInfo(settings.app_timezone)

def _market_phase(now: datetime) -> str:
    local_now = now.astimezone(IST) if now.tzinfo else now.replace(tzinfo=IST)
    t = local_now.time()
    if t < time(9, 0):
        return "PRE_MARKET"
    if t < time(9, 20):
        return "OPENING"
    if t < time(11, 0):
        return "MORNING_TREND"
    if t < time(13, 0):
        return "MIDDAY"
    if t < time(14, 30):
        return "AFTERNOON"
    if t < time(15, 30):
        return "POWER_HOUR"
    return "MARKET_CLOSED"


def _build_checklist(f: Features, dominant: Direction, htf: AgentResult, options: AgentResult,
                      trap_label: str, rr_ok: bool) -> list[EntryChecklistItem]:
    items = []
    items.append(EntryChecklistItem("HTF aligned", htf.direction == dominant, htf.reason))
    items.append(EntryChecklistItem(
        "Above VWAP" if dominant == Direction.BULLISH else "Below VWAP",
        (f.close > f.vwap) if dominant == Direction.BULLISH else (f.close < f.vwap),
        f"Close {f.close:.1f} vs VWAP {f.vwap:.1f}",
    ))
    items.append(EntryChecklistItem(
        "EMA aligned",
        (f.ema20 > f.ema50) if dominant == Direction.BULLISH else (f.ema20 < f.ema50),
        f"EMA20 {f.ema20:.1f} vs EMA50 {f.ema50:.1f}",
    ))
    items.append(EntryChecklistItem("Momentum confirmed", f.relative_volume > 1.0, f"Relative volume {f.relative_volume:.2f}x"))
    items.append(EntryChecklistItem("Options supportive", options.direction == dominant, options.reason))
    items.append(EntryChecklistItem("No trap risk", trap_label == "NO_TRAP", f"Trap status: {trap_label}"))
    items.append(EntryChecklistItem("Risk/Reward acceptable", rr_ok, f"Minimum RR: {settings.min_risk_reward}"))
    return items


def _build_trade_plan(f: Features, dominant: Direction, option_snapshot: dict) -> tuple[TradePlan | None, float | None]:
    """Builds a real plan using actual chain LTPs (never fabricated prices).
    Returns (plan, risk_reward) — plan is None if we can't price it honestly."""
    chain = option_snapshot.get("chain", {})
    atm = option_snapshot.get("atm")
    side = "CE" if dominant == Direction.BULLISH else "PE"
    leg_list = chain.get(side, [])
    leg = next((x for x in leg_list if x["strike"] == atm), None)
    if leg is None or leg.get("ltp") is None:
        return None, None

    ltp = leg["ltp"]
    entry_low = round(ltp * 0.98, 2)
    entry_high = round(ltp * 1.02, 2)
    stop = round(ltp * 0.85, 2)   # 15% risk
    t1 = round(ltp * 1.25, 2)     # 25% reward -> RR ~1.67 at T1
    t2 = round(ltp * 1.45, 2)     # 45% reward at T2
    risk = ltp - stop
    reward = t1 - ltp
    rr = round(reward / risk, 2) if risk > 0 else None

    trigger = "3m close above ORH" if side == "CE" else "3m close below ORL"
    invalidation = "Nifty closes below VWAP" if side == "CE" else "Nifty closes above VWAP"

    plan = TradePlan(
        option_type=side, strike=atm, ltp=ltp, entry_low=entry_low, entry_high=entry_high,
        trigger=trigger, confirmation=f"Volume > 1.3x average (currently {f.relative_volume:.2f}x)",
        stop_loss=stop, target_1=t1, target_2=t2, risk_reward=rr,
        max_risk_rupees=round((ltp - stop) * int(leg.get("lot_size") or settings.nifty_lot_size), 2),
        invalidation=invalidation,
        delta=leg.get("delta"), theta=leg.get("theta"), iv=leg.get("iv"),
    )
    return plan, rr



def _pipeline_now(as_of: datetime | None = None) -> datetime:
    """
    Resolve the effective decision time.

    Live mode:
        as_of=None -> current UTC wall clock.

    Replay mode:
        as_of=<historical timestamp> -> deterministic historical clock.

    Naive timestamps are interpreted as UTC rather than using local
    server timezone implicitly.
    """
    value = as_of or datetime.now(timezone.utc)

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def run_pipeline(data_source: DataSource, position: PositionInfo | None = None, as_of: datetime | None = None) -> LiveDecisionResponse:
    now = _pipeline_now(as_of)
    components: list[ComponentHealth] = []

    # ---- 1. fetch market data (fail loud, never fabricate) -----------
    try:
        df_3m = data_source.get_ohlc("3m", 150)
        df_1d = data_source.get_ohlc("1d", 5)
        spot = data_source.get_spot()
        vix = data_source.get_vix()
        option_snapshot = data_source.get_option_chain(atm_range=5)
        last_tick = data_source.get_last_tick_timestamp()
        components.append(ComponentHealth("Market Data", HealthStatus.GREEN, f"source={data_source.source_name}"))
    except DataUnavailable as e:
        components.append(ComponentHealth("Market Data", HealthStatus.RED, str(e)))
        return _no_trade_response(str(e), components, now)

    days_to_expiry = _days_to_expiry(option_snapshot.get("expiry"), now)
    if days_to_expiry is not None and option_snapshot.get("chain"):
        try:
            option_snapshot["chain"] = greeks_module.enrich_chain_with_greeks(
                option_snapshot["chain"], spot=spot, days_to_expiry=days_to_expiry,
            )
            components.append(ComponentHealth("Greeks Engine", HealthStatus.GREEN, f"backend={greeks_module.backend_name()}"))
        except Exception as e:
            # Greeks are supplementary — never let a pricing-model failure
            # take down the whole decision pipeline. Legs simply keep
            # delta/gamma/theta/vega=None (schema default), never a guess.
            components.append(ComponentHealth("Greeks Engine", HealthStatus.AMBER, f"enrichment failed: {e}"))
    else:
        components.append(ComponentHealth("Greeks Engine", HealthStatus.AMBER, "no expiry date available from data source"))

    last_tick_dt = datetime.fromisoformat(last_tick.replace("Z", "+00:00"))
    if last_tick_dt.tzinfo is None:
        last_tick_dt = last_tick_dt.replace(tzinfo=timezone.utc)
    data_age_sec = max(
        0.0,
        (now - last_tick_dt.astimezone(timezone.utc)).total_seconds()
    )
    if data_age_sec > settings.max_data_age_sec:
        components.append(ComponentHealth("Data Freshness", HealthStatus.RED, f"{data_age_sec:.1f}s stale"))
    else:
        components.append(ComponentHealth("Data Freshness", HealthStatus.GREEN, f"{data_age_sec:.1f}s"))

    f = build_features(df_3m, df_1d)

    # V7.2 NIFTY Futures participation intelligence.
    # Spot remains authoritative for price/EMA/RSI/MACD/ADX/ATR.
    # Futures supplies genuine VWAP, traded volume and RVOL.
    # Fail-open: Futures failure must not break V7.1 behavior.
    try:
        futures_df, _futures_meta = load_nifty_futures_ohlc(
            data_source,
            timeframe="3m",
            lookback=120,
        )

        futures_snapshot = build_futures_volume_snapshot(
            futures_df,
            spot_close=float(f.close),
        )

        if futures_snapshot.get("status") == "READY":
            f = merge_futures_volume_into_features(
                f,
                futures_snapshot,
            )

    except Exception:
        # Keep original spot-only Features when Futures data fails.
        # Never fabricate missing market information.
        pass

    # ---- 2. multi-timeframe candles for HTF Bias Agent ----------------
    candles_by_tf = {"3m": df_3m}
    for tf in ["5m", "15m", "1d"]:
        try:
            candles_by_tf["daily" if tf == "1d" else tf] = data_source.get_ohlc(tf, 100)
        except DataUnavailable:
            pass  # HTF agent handles missing timeframes gracefully, never fabricates

    # ---- 3. run agents --------------------------------------------------
    w = settings.agent_weights
    htf = htf_bias_agent(candles_by_tf, w["Higher Timeframe Bias Agent"])
    regime, regime_label = regime_agent(f, w["Regime Agent"])
    trend = trend_agent(f, w["Trend Agent"])
    momentum = momentum_agent(f, w["Momentum Agent"])
    liquidity, liq_metrics = liquidity_agent(f, df_3m, w["Liquidity Agent"])
    options_oi, oi_metrics = options_oi_agent(option_snapshot, w["Options/OI Agent"])
    gamma, gamma_metrics = gamma_agent(option_snapshot, oi_metrics, spot, w["Gamma Agent"])
    trap, trap_label = trap_detection_agent(f, df_3m, w["Trap Detection Agent"])
    structure = analyse_market_structure(df_3m)

    agents = [htf, regime, trend, momentum, liquidity, options_oi, gamma, trap]

    # ---- 4. alignment + provisional direction --------------------------
    alignment = compute_alignment(agents, w, regime_label=regime_label)
    directional = [a for a in agents if a.direction in (Direction.BULLISH, Direction.BEARISH) and a.score is not None]
    bull_weight = sum(w.get(a.name, 0) for a in directional if a.direction == Direction.BULLISH)
    bear_weight = sum(w.get(a.name, 0) for a in directional if a.direction == Direction.BEARISH)
    dominant = Direction.BULLISH if bull_weight > bear_weight else (Direction.BEARISH if bear_weight > bull_weight else Direction.NEUTRAL)
    conflicting = sum(1 for a in directional if a.direction != dominant)

    # ---- 5. tentative plan (needed to know RR before risk check) -------
    plan, rr = (None, None)
    if dominant != Direction.NEUTRAL:
        plan, rr = _build_trade_plan(f, dominant, option_snapshot)

    minutes_to_close = None
    now_ist = now.astimezone(IST)
    market_close = datetime.combine(now_ist.date(), time(15, 30), tzinfo=IST)
    if now_ist < market_close:
        minutes_to_close = (market_close - now_ist).total_seconds() / 60

    session = store.get_session_dict()
    risk_agent_result, risk_result = risk_agent(
        trades_today=session["trades_today"], max_trades=settings.max_trades_per_day,
        daily_pnl=session["daily_pnl"], daily_loss_limit=settings.daily_loss_limit,
        consecutive_losses=session["consecutive_losses"], max_consecutive_losses=settings.max_consecutive_losses,
        data_age_sec=data_age_sec, max_data_age_sec=settings.max_data_age_sec,
        vix=vix, vix_spike_threshold=settings.vix_spike_threshold,
        proposed_rr=rr, min_rr=settings.min_risk_reward,
        minutes_to_close=minutes_to_close, weight=w["Risk Agent"],
    )
    agents.append(risk_agent_result)
    alignment = compute_alignment(agents, w, regime_label=regime_label)  # recompute including risk agent
    debate = build_debate(agents, w)

    # ---- 6. grade + final decision --------------------------------------
    grade = classify_trade_grade(
        alignment, risk_result.approved, dominant, conflicting,
        min_coverage=settings.min_agent_coverage,
        max_disagreement=settings.max_agent_disagreement,
    )
    rr_ok = rr is not None and rr >= settings.min_risk_reward
    checklist = _build_checklist(f, dominant, htf, options_oi, trap_label, rr_ok)
    checks_passed = all(c.passed for c in checklist)

    if grade in (TradeGrade.A_PLUS, TradeGrade.A) and dominant != Direction.NEUTRAL and checks_passed and plan is not None:
        decision_type = DecisionType.CE_BUY if dominant == Direction.BULLISH else DecisionType.PE_BUY
        explanation = (
            f"{decision_type.value.replace('_',' ')} qualifies as grade {grade.value}. "
            f"Alignment {alignment.score}/100 with {len([c for c in checklist if c.passed])}/{len(checklist)} "
            f"checklist items passed. {htf.reason}"
        )
    else:
        decision_type = DecisionType.NO_TRADE
        grade = TradeGrade.NO_TRADE if grade in (TradeGrade.A_PLUS, TradeGrade.A) and not checks_passed else grade
        failed = [c.label for c in checklist if not c.passed]
        reasons = []
        if not risk_result.approved:
            reasons.append("Risk Agent vetoed: " + "; ".join(risk_result.reasons))
        if conflicting >= 3:
            reasons.append(f"{conflicting} agents disagree with the dominant direction")
        if alignment.coverage_ratio < settings.min_agent_coverage:
            reasons.append(f"Agent coverage too low ({alignment.coverage_ratio:.0%})")
        if alignment.disagreement_score > settings.max_agent_disagreement:
            reasons.append(f"Agent disagreement too high ({alignment.disagreement_score:.0%})")
        if failed:
            reasons.append(f"Failed checklist items: {', '.join(failed)}")
        if alignment.score is not None and alignment.score < 55:
            reasons.append(f"Alignment score too low ({alignment.score}/100)")
        explanation = " ".join(reasons) if reasons else "No high-probability setup currently qualifies. Waiting for stronger alignment."
        plan = None

    decision = Decision(
        decision=decision_type, grade=grade, confidence=alignment.calibrated_confidence,
        alignment_score=alignment.score, plan=plan, checklist=checklist, explanation=explanation,
    )

    flags = build_flags(f, trend.direction, momentum.direction, trap_label,
                         float(df_3m["high"][df_3m["high"] > f.close].max()) if (df_3m["high"] > f.close).any() else f.session_high,
                         options_oi.direction.value)

    components.append(ComponentHealth("Agent Engine", HealthStatus.GREEN, f"{len(agents)} agents evaluated"))
    system_health = SystemHealth(
        components=components, last_tick_timestamp=last_tick, data_age_sec=round(data_age_sec, 2),
        overall=HealthStatus.RED if any(c.status == HealthStatus.RED for c in components) else HealthStatus.GREEN,
    )

    evidence_row = df_3m.iloc[-1]
    evidence_timestamp = df_3m.index[-1]
    if hasattr(evidence_timestamp, "to_pydatetime"):
        evidence_timestamp = evidence_timestamp.to_pydatetime()
    decision_evidence = build_decision_evidence(
        {"timestamp": evidence_timestamp.isoformat(), "finalized": True,
         "open": evidence_row["open"], "high": evidence_row["high"],
         "low": evidence_row["low"], "close": evidence_row["close"],
         "volume": evidence_row.get("volume", 0), "ticks": 0},
        {"regime": regime_label, "alignment_score": alignment.score,
         "decision": decision_type.value, "grade": grade.value,
         "vwap": round(f.vwap, 6), "ema20": round(f.ema20, 6),
         "ema50": round(f.ema50, 6), "rsi14": round(f.rsi14, 6), "atr14": round(f.atr14, 6)},
    )
    response = LiveDecisionResponse(
        timestamp=now.isoformat(),
        decision_evidence=decision_evidence,
        market={
            "spot": spot, "vix": vix, "phase": _market_phase(now), "source": data_source.source_name,
            "day_change": round(f.close - f.pdc, 2), "day_change_pct": round((f.close - f.pdc) / f.pdc * 100, 2),
        },
        regime={"label": regime_label, "reason": regime.reason, "score": regime.score, "direction": regime.direction.value},
        levels={
            "pdh": f.pdh, "pdl": f.pdl, "pdc": f.pdc, "today_open": f.day_open,
            "vwap": round(f.vwap, 2), "ema20": round(f.ema20, 2), "ema50": round(f.ema50, 2),
            "session_high": f.session_high, "session_low": f.session_low,
            "call_wall": oi_metrics.get("call_wall", {}).get("strike") if oi_metrics else None,
            "put_wall": oi_metrics.get("put_wall", {}).get("strike") if oi_metrics else None,
        },
        indicators={
            "rsi14": round(f.rsi14, 1), "macd_hist": round(f.macd_hist, 2), "adx14": round(f.adx14, 1),
            "atr14": round(f.atr14, 2), "ema20": round(f.ema20, 2), "ema50": round(f.ema50, 2),
            "vwap": round(f.vwap, 2), "volume": f.volume, "relative_volume": round(f.relative_volume, 2),
        },
        options={"snapshot": option_snapshot, "metrics": oi_metrics},
        gamma={"agent": gamma.reason, "score": gamma.score, **gamma_metrics},
        liquidity={"agent": liquidity.reason, "score": liquidity.score, **liq_metrics},
        agents=agents,
        alignment=alignment,
        debate={
            "bull_case": debate.bull_case, "bear_case": debate.bear_case,
            "neutral_case": debate.neutral_case, "bullish_weight": debate.bullish_weight,
            "bearish_weight": debate.bearish_weight, "disagreement_score": debate.disagreement_score,
            "coverage_ratio": debate.coverage_ratio, "dominant_direction": debate.dominant_direction.value,
            "conflicting_agents": debate.conflicting_agents, "family_directions": debate.family_directions,
        },
        flags=flags,
        decision=decision,
        risk=risk_result,
        position=position or PositionInfo(has_position=False),
        system_health=system_health,
        market_structure={
            "trend": structure.trend,
            "sequence_labels": structure.sequence_labels,
            "last_event": structure.last_event,
            "last_event_detail": structure.last_event_detail,
            "swings": [{"time": s.time, "price": s.price, "kind": s.kind} for s in structure.swings],
            "fvgs": structure.fvgs,
            "order_blocks": structure.order_blocks,
            "candlestick_patterns": structure.candlestick_patterns,
        },
        narrative=build_narrative(
            f, regime_label, trend.direction.value, oi_metrics,
            liq_metrics.get("buy_side_liquidity", f.session_high),
            liq_metrics.get("sell_side_liquidity", f.session_low),
            trap_label,
        ),
    )
    return response


def _no_trade_response(reason: str, components: list[ComponentHealth], now: datetime) -> LiveDecisionResponse:
    """Used when market data itself is unavailable — every agent reports
    NOT_AVAILABLE rather than the pipeline crashing or guessing."""
    from app.agents.base import not_available
    w = settings.agent_weights
    agents = [not_available(name, weight, "Market data unavailable") for name, weight in w.items()]
    system_health = SystemHealth(components=components, last_tick_timestamp=None, data_age_sec=None, overall=HealthStatus.RED)
    decision = Decision(
        decision=DecisionType.NO_TRADE, grade=TradeGrade.NO_TRADE, confidence=None, alignment_score=None,
        plan=None, checklist=[], explanation=f"NO TRADE — market data unavailable: {reason}",
    )
    session = store.get_session_dict()
    risk_result = RiskResult(approved=False, reasons=[f"Data unavailable: {reason}"], trades_today=session["trades_today"],
                              max_trades=settings.max_trades_per_day, daily_pnl=session["daily_pnl"],
                              daily_loss_limit=settings.daily_loss_limit, consecutive_losses=session["consecutive_losses"])
    return LiveDecisionResponse(
        timestamp=now.isoformat(), decision_evidence={}, market={"status": "DATA_ERROR", "reason": reason}, regime={}, levels={},
        indicators={}, options={}, gamma={}, liquidity={}, agents=agents,
        alignment=compute_alignment(agents, w), debate={"bull_case": [], "bear_case": [], "neutral_case": [], "coverage_ratio": 0.0, "disagreement_score": 0.0, "dominant_direction": "NEUTRAL"}, flags=[], decision=decision, risk=risk_result,
        position=PositionInfo(has_position=False), system_health=system_health,
        market_structure={}, narrative="NOT AVAILABLE — market data unavailable.",
    )
