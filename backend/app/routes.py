from __future__ import annotations
import asyncio
import json
from dataclasses import asdict
from typing import Literal
import hashlib
from pydantic import BaseModel, Field, model_validator
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Header, Depends
from fastapi.responses import Response
from app.config import settings, validate
from app.pipeline import run_pipeline
from app.observability import run_observed_pipeline, metrics_snapshot, list_alerts
from app.schemas import LiveDecisionResponseSchema, from_dataclass
from app.data_sources.mock_source import MockDataSource
from app.audit_log import log_decision
from app.analytics import todays_skip_and_block_counts
from app import store
from app.version import version_info
from app.risk_supervisor import evaluate_paper_entry, status as risk_status
from app.option_chain_intelligence import analyse_option_chain
from app.release_health import release_certificate
from app.decision_explainability import explain_decision
from app.institutional_flow import analyse_institutional_flow, classify_buildup
from app.institutional_flow_history import (
    record_flow_snapshot, list_flow_history, flow_trend, recent_anomalies,
)
from app.market_regime_engine import classify_market_regime
from app.smart_money_engine import analyse_market_structure
from app.gamma_intelligence import analyse_gamma
from app.ai_supervisor_v2 import build_supervisor_decision

router = APIRouter()


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.admin_token:
        if settings.is_live():
            raise HTTPException(status_code=503, detail="ADMIN_TOKEN is not configured")
        return
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")

_data_source = None


def get_data_source():
    """Single place that decides mock vs live, per config.py canonical
    settings — never instantiated ad-hoc elsewhere."""
    global _data_source
    if _data_source is not None:
        return _data_source
    if settings.is_live():
        from app.data_sources.zerodha_client import ZerodhaDataSource
        _data_source = ZerodhaDataSource(
            api_key=settings.kite_api_key, access_token=settings.kite_access_token,
        )
    else:
        _data_source = MockDataSource()
    return _data_source


def _current_position_info():
    """Builds a live PositionInfo from the SQLite store, marking to market
    against the current option-chain LTP for the held strike when available."""
    from app.models import PositionInfo
    open_pos = store.get_open_position()
    if not open_pos:
        return PositionInfo(has_position=False)

    current_price = open_pos["entry_price"]
    try:
        ds = get_data_source()
        snap = ds.get_option_chain(atm_range=8)
        leg = next(
            (x for x in snap["chain"].get(open_pos["option_type"], [])
             if x["strike"] == open_pos["strike"]), None,
        )
        if leg and leg.get("ltp") is not None:
            current_price = leg["ltp"]
    except Exception:
        pass  # keep entry_price as a safe fallback rather than crash the endpoint

    pnl = (current_price - open_pos["entry_price"]) * open_pos["quantity"]
    pnl_pct = round((current_price - open_pos["entry_price"]) / open_pos["entry_price"] * 100, 2)
    from datetime import datetime, timezone
    opened_at = datetime.fromisoformat(open_pos["opened_at"])
    time_in_trade = int((datetime.now(timezone.utc) - opened_at).total_seconds())

    return PositionInfo(
        has_position=True, option_type=open_pos["option_type"], strike=open_pos["strike"],
        quantity=open_pos["quantity"], entry_price=open_pos["entry_price"], current_price=current_price,
        pnl=round(pnl, 2), pnl_pct=pnl_pct, stop_loss=open_pos["stop_loss"],
        target_1=open_pos["target_1"], target_2=open_pos["target_2"], status="OPEN",
        time_in_trade_sec=time_in_trade,
    )


_last_logged_signature = None


def _decision_signature(resp) -> tuple:
    return (resp.decision.decision.value, resp.decision.grade.value, resp.alignment.score, resp.risk.approved)


@router.get("/api/decision/live", response_model=LiveDecisionResponseSchema)
def get_live_decision():
    resp = _build_and_log_live_decision()
    return from_dataclass(resp)


@router.get("/api/market/snapshot")
def get_market_snapshot():
    ds = get_data_source()
    resp = run_observed_pipeline(run_pipeline, ds)
    return {"market": resp.market, "levels": resp.levels, "indicators": resp.indicators,
            "timestamp": resp.timestamp}


@router.get("/api/agents/status")
def get_agents_status():
    ds = get_data_source()
    resp = run_observed_pipeline(run_pipeline, ds)
    return {"agents": [asdict(a) for a in resp.agents], "alignment": asdict(resp.alignment)}


@router.get("/api/options/snapshot")
def get_options_snapshot():
    ds = get_data_source()
    resp = run_observed_pipeline(run_pipeline, ds)
    return resp.options




@router.get("/api/option-chain/live")
def get_option_chain_live(atm_range: int = 8):
    if atm_range < 2 or atm_range > 20:
        raise HTTPException(status_code=422, detail="atm_range must be between 2 and 20")
    ds = get_data_source()
    snapshot = ds.get_option_chain(atm_range=atm_range)
    return {**snapshot, "intelligence": analyse_option_chain(snapshot)}


@router.get("/api/option-chain/summary")
def get_option_chain_summary(atm_range: int = 8):
    if atm_range < 2 or atm_range > 20:
        raise HTTPException(status_code=422, detail="atm_range must be between 2 and 20")
    ds = get_data_source()
    snapshot = ds.get_option_chain(atm_range=atm_range)
    return analyse_option_chain(snapshot)


@router.get("/api/option-chain/support-resistance")
def get_option_chain_support_resistance(atm_range: int = 8):
    ds = get_data_source()
    summary = analyse_option_chain(ds.get_option_chain(atm_range=atm_range))
    return {
        "spot": summary["spot"],
        "atm_strike": summary["atm_strike"],
        "support": summary["strongest_support"],
        "resistance": summary["strongest_resistance"],
        "put_wall": summary["put_wall"],
        "call_wall": summary["call_wall"],
        "max_pain": summary["max_pain"],
        "bias": summary["institutional_bias"],
        "bias_score": summary["bias_score"],
    }


@router.get("/api/option-chain/max-pain")
def get_option_chain_max_pain(atm_range: int = 8):
    ds = get_data_source()
    summary = analyse_option_chain(ds.get_option_chain(atm_range=atm_range))
    return {"spot": summary["spot"], "atm_strike": summary["atm_strike"], "max_pain": summary["max_pain"], "expiry": summary["expiry"]}




@router.get("/api/ai-command-center")
def get_ai_command_center():
    response = _build_and_log_live_decision()
    ds = get_data_source()
    option_snapshot = ds.get_option_chain(atm_range=8)
    option_summary = analyse_option_chain(option_snapshot)
    institutional = analyse_institutional_flow(option_summary)
    candles = []
    try:
        from app.market_data_service import get_supervisor
        candles = get_supervisor(
            settings.market_data_state_path, settings.market_data_poll_interval_sec,
            settings.max_data_age_sec, settings.kite_websocket_requested,
        ).snapshot().get("candles_3m", [])
    except Exception:
        candles = []
    if len(candles) < 5:
        # Use a conservative synthetic sequence derived from current market values only for
        # structure availability in demo mode; live mode keeps the insufficient-data warning.
        if not settings.is_live():
            spot = float(response.market.get("nifty_spot") or 0.0)
            candles = [{"open": spot+i-2, "high": spot+i+2, "low": spot+i-4, "close": spot+i} for i in range(6)]
    regime = classify_market_regime(response.market, response.indicators, response.levels)
    structure = analyse_market_structure(candles)
    gamma = analyse_gamma(option_snapshot, settings.nifty_lot_size)
    return build_supervisor_decision(response, regime, structure, gamma, institutional)


@router.get("/api/market-regime/intelligence")
def get_market_regime_intelligence():
    response = _build_and_log_live_decision()
    return classify_market_regime(response.market, response.indicators, response.levels)


@router.get("/api/gamma/intelligence")
def get_gamma_intelligence(atm_range: int = 8):
    return analyse_gamma(get_data_source().get_option_chain(atm_range=atm_range), settings.nifty_lot_size)


@router.post("/api/smart-money/analyse")
def post_smart_money_analysis(payload: dict):
    candles = payload.get("candles") or []
    return analyse_market_structure(candles)

@router.get("/api/institutional-flow/summary")
def get_institutional_flow_summary(atm_range: int = 8):
    if atm_range < 2 or atm_range > 20:
        raise HTTPException(status_code=422, detail="atm_range must be between 2 and 20")
    ds = get_data_source()
    option_summary = analyse_option_chain(ds.get_option_chain(atm_range=atm_range))
    summary = analyse_institutional_flow(option_summary)
    snapshot = record_flow_snapshot(summary, option_summary)
    return {**summary, "snapshot_id": snapshot["id"], "captured_at": snapshot["captured_at"], "anomaly": snapshot["anomaly"]}


@router.post("/api/institutional-flow/analyse")
def post_institutional_flow_analysis(payload: dict):
    option_summary = payload.get("option_summary") or {}
    if not option_summary:
        ds = get_data_source()
        option_summary = analyse_option_chain(ds.get_option_chain(atm_range=8))
    return analyse_institutional_flow(
        option_summary, payload.get("futures"), payload.get("cash"), payload.get("pcr_history")
    )


@router.get("/api/institutional-flow/history")
def get_institutional_flow_history(limit: int = 120, trading_day: str | None = None):
    return {"history": list_flow_history(limit=limit, trading_day=trading_day)}


@router.get("/api/institutional-flow/trend")
def get_institutional_flow_trend(limit: int = 120, trading_day: str | None = None):
    return flow_trend(limit=limit, trading_day=trading_day)


@router.get("/api/institutional-flow/anomalies")
def get_institutional_flow_anomalies(limit: int = 20):
    return {"anomalies": recent_anomalies(limit=limit)}


@router.get("/api/decision/intelligence")
def get_decision_intelligence():
    response = _build_and_log_live_decision()
    option_summary = None
    flow = None
    try:
        option_summary = analyse_option_chain(get_data_source().get_option_chain(atm_range=8))
        flow = analyse_institutional_flow(option_summary)
        record_flow_snapshot(flow, option_summary)
    except Exception:
        flow = None
    base_confidence = float(response.decision.confidence or 0.0)
    adjusted = base_confidence
    checks = []
    decision = response.decision.decision.value
    if flow:
        flow_bias = flow.get("institutional_bias")
        confirms = (decision == "CE_BUY" and flow_bias == "BULLISH") or (decision == "PE_BUY" and flow_bias == "BEARISH")
        conflicts = decision != "NO_TRADE" and flow_bias not in {"NEUTRAL", None} and not confirms
        if confirms:
            adjusted = min(100.0, adjusted + min(12.0, float(flow.get("confidence") or 0.0) * 0.12))
            checks.append({"name":"Institutional flow confirms", "passed":True, "detail":f"{flow_bias} score {flow.get('institutional_flow_score')}"})
        elif conflicts:
            adjusted = max(0.0, adjusted - min(18.0, abs(float(flow.get("institutional_flow_score") or 0.0)) * 0.18))
            checks.append({"name":"Institutional flow confirms", "passed":False, "detail":f"Flow bias {flow_bias} conflicts with {decision}"})
        else:
            checks.append({"name":"Institutional flow confirms", "passed":False, "detail":"Flow evidence is neutral or the system is waiting"})
        if flow.get("warnings"):
            adjusted = max(0.0, adjusted - min(8.0, len(flow["warnings"]) * 2.0))
    return {
        "decision": decision, "base_confidence": round(base_confidence,2),
        "adjusted_confidence": round(adjusted,2), "institutional_flow": flow,
        "option_chain": option_summary, "checks": checks,
        "execution_mode":"DECISION_SUPPORT_ONLY", "live_orders_enabled":False,
    }


@router.get("/api/institutional-flow/buildup")
def get_buildup_classification(price_change_pct: float, oi_change_pct: float):
    return {"classification": classify_buildup(price_change_pct, oi_change_pct),
            "price_change_pct": price_change_pct, "oi_change_pct": oi_change_pct}

@router.get("/api/positions/current")
def get_positions_current():
    return asdict(_current_position_info())


class OpenPositionRequest(BaseModel):
    option_type: Literal["CE", "PE"]
    strike: int = Field(gt=0)
    quantity: int = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    target_1: float | None = Field(default=None, gt=0)
    target_2: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_levels(self):
        if self.stop_loss is not None and self.stop_loss >= self.entry_price:
            raise ValueError("stop_loss must be below entry_price for long option buying")
        if self.target_1 is not None and self.target_1 <= self.entry_price:
            raise ValueError("target_1 must be above entry_price")
        if self.target_1 is not None and self.target_2 is not None and self.target_2 <= self.target_1:
            raise ValueError("target_2 must be above target_1")
        return self


@router.post("/api/positions/open", dependencies=[Depends(require_admin_token)])
def open_position(body: OpenPositionRequest):
    try:
        pos_id = store.open_position(
            body.option_type, body.strike, body.quantity, body.entry_price,
            body.stop_loss, body.target_1, body.target_2,
        )
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(status_code=409, detail="A position is already open") from exc
        raise
    return {"id": pos_id, "status": "OPEN"}


class ClosePositionRequest(BaseModel):
    close_price: float = Field(gt=0)
    status: Literal["CLOSED_TARGET", "CLOSED_SL", "CLOSED_MANUAL"] = "CLOSED_MANUAL"
    grade: Literal["A+", "A", "B", "NO_TRADE"] = "B"


@router.post("/api/positions/close", dependencies=[Depends(require_admin_token)])
def close_position(body: ClosePositionRequest):
    open_pos = store.get_open_position()
    if not open_pos:
        raise HTTPException(status_code=404, detail="No open position to close.")
    closed = store.close_position(open_pos["id"], body.close_price, body.status)
    store.record_trade_result(closed["pnl"], body.grade)
    return closed


@router.get("/api/analytics/session")
def get_analytics_session():
    s = store.get_session_dict()
    skipped, blocked = todays_skip_and_block_counts()
    win_rate = round(s["wins"] / s["trades_today"] * 100, 1) if s["trades_today"] else None
    avg_rr = None  # requires per-trade RR history; add once trade log includes it
    return {
        "trades_today": s["trades_today"], "wins": s["wins"], "losses": s["losses"],
        "win_rate": win_rate, "gross_pnl": s["gross_pnl"], "net_pnl": s["daily_pnl"],
        "avg_rr": avg_rr, "best_trade": s["best_trade"], "worst_trade": s["worst_trade"],
        "a_plus_trades": s["a_plus_trades"], "a_trades": s["a_trades"],
        "skipped_setups": skipped, "risk_blocked_setups": blocked,
    }


@router.get("/api/system/health")
def get_system_health():
    ds = get_data_source()
    resp = run_observed_pipeline(run_pipeline, ds)
    return asdict(resp.system_health)


@router.get("/api/system/config-check")
def config_check():
    problems = validate()
    return {"ok": len(problems) == 0, "problems": problems, "trading_mode": settings.trading_mode, **version_info()}


@router.get("/api/system/version")
def system_version():
    return version_info()


@router.get("/api/system/release-certificate")
def system_release_certificate():
    return release_certificate()


@router.get("/api/decision/explain")
def get_decision_explanation():
    response = _build_and_log_live_decision()
    snapshot = None
    try:
        snapshot = get_data_source().get_option_chain(atm_range=8)
    except Exception:
        pass
    return explain_decision(response, snapshot)


@router.get("/api/system/metrics")
def system_metrics():
    return metrics_snapshot()


@router.get("/api/system/alerts")
def system_alerts(limit: int = 50):
    return {"alerts": list_alerts(limit)}


@router.get("/api/system/zerodha-health")
def zerodha_health():
    ds = get_data_source()
    if hasattr(ds, "token_health"):
        return ds.token_health()
    return {"connected": True, "source": ds.source_name, "mode": settings.trading_mode}


@router.get("/api/setups")
def list_setups(trading_day: str | None = None, status: str | None = None, limit: int = 50):
    return {"setups": store.list_trade_setups(trading_day=trading_day, status=status, limit=limit)}


class ReviewSetupRequest(BaseModel):
    status: Literal["APPROVED", "REJECTED", "EXPIRED", "CANCELLED"]
    note: str | None = Field(default=None, max_length=500)


@router.post("/api/setups/{setup_id}/review", dependencies=[Depends(require_admin_token)])
def review_setup(setup_id: int, body: ReviewSetupRequest):
    try:
        result = store.review_trade_setup(setup_id, body.status, body.note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Trade setup not found")
    return result



class PaperExecuteRequest(BaseModel):
    setup_id: int = Field(gt=0)
    entry_price: float = Field(gt=0)
    quantity: int | None = Field(default=None, gt=0)


@router.post("/api/paper/execute", dependencies=[Depends(require_admin_token)])
def execute_paper_trade(body: PaperExecuteRequest):
    setup = store.get_trade_setup(body.setup_id)
    if setup is None:
        raise HTTPException(status_code=404, detail="Trade setup not found")
    decision = evaluate_paper_entry(setup, body.entry_price, body.quantity)
    if not decision.approved:
        raise HTTPException(status_code=409, detail={"message": "Risk supervisor blocked the trade", **decision.to_dict()})
    try:
        trade_id = store.open_paper_trade(body.setup_id, decision.requested_quantity, body.entry_price, settings.paper_slippage_rupees)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(status_code=409, detail="A paper trade is already open") from exc
        raise
    from app.paper_trade_management import ensure_management
    trade = store.get_open_paper_trade()
    management = ensure_management(trade) if trade else None
    return {
        "id": trade_id, "status": "OPEN", "quantity": decision.requested_quantity,
        "effective_entry": round(body.entry_price + settings.paper_slippage_rupees, 2),
        "risk": decision.to_dict(), "management": management, "execution_mode": "PAPER_ONLY",
    }


@router.get("/api/paper/trades")
def paper_trades(trading_day: str | None = None, status: str | None = None, limit: int = 50):
    return {"trades": store.list_paper_trades(trading_day, status, limit)}


@router.get("/api/paper/portfolio")
def paper_portfolio(trading_day: str | None = None):
    return store.paper_portfolio_summary(trading_day)


@router.get("/api/paper/journal")
def paper_journal(trading_day: str | None = None, limit: int = 200):
    from app.paper_journal import journal_rows
    return {"trades": journal_rows(trading_day=trading_day, limit=limit), "execution_mode": "PAPER_ONLY"}


@router.get("/api/paper/journal.csv")
def paper_journal_csv(trading_day: str | None = None, limit: int = 200):
    from app.paper_journal import journal_csv
    body = journal_csv(trading_day=trading_day, limit=limit)
    filename = f"paper-journal-{trading_day or 'all'}.csv"
    return Response(content=body, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/api/paper/daily-summary")
def paper_daily_summary(trading_day: str | None = None):
    from app.paper_journal import daily_summary
    return daily_summary(trading_day=trading_day)


@router.get("/api/paper/trades/{trade_id}/timeline")
def paper_trade_timeline(trade_id: int):
    result = store.get_trade_timeline(trade_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Paper trade not found")
    return result


class PaperCloseRequest(BaseModel):
    close_price: float = Field(gt=0)
    reason: str = Field(default="MANUAL", min_length=1, max_length=100)


@router.post("/api/paper/close", dependencies=[Depends(require_admin_token)])
def close_paper_trade_manual(body: PaperCloseRequest):
    trade = store.get_open_paper_trade()
    if not trade:
        raise HTTPException(status_code=404, detail="No open paper trade")
    from app.paper_trade_management import close_manually
    closed = close_manually(trade, body.close_price, body.reason)
    if closed is None:
        raise HTTPException(status_code=409, detail="Paper trade is already closed")
    store.record_trade_result(closed["net_pnl"], "B")
    store.record_paper_monitor_event(trade["id"], body.close_price, "CLOSED", body.reason)
    return closed


class PaperMonitorRequest(BaseModel):
    current_price: float = Field(gt=0)
    force_eod: bool = False


@router.post("/api/paper/monitor", dependencies=[Depends(require_admin_token)])
def monitor_paper_trade(body: PaperMonitorRequest):
    trade = store.get_open_paper_trade()
    if not trade:
        return {"action": "NONE", "detail": "No open paper trade"}
    from app.paper_trade_management import evaluate
    result = evaluate(trade, body.current_price, force_eod=body.force_eod)
    detail = ",".join(result.get("actions") or []) or result.get("reason")
    store.record_paper_monitor_event(trade["id"], body.current_price, result["action"], detail)
    if result["action"] == "CLOSED" and result.get("net_pnl") is not None:
        store.record_trade_result(result["net_pnl"], "B")
    return result


@router.get("/api/paper/management/status")
def paper_management_status():
    from app.paper_trade_management import get_open_management
    state = get_open_management()
    return state or {"trade": None, "management": None, "execution_mode": "PAPER_ONLY"}


class PaperManagementConfigRequest(BaseModel):
    trailing_enabled: bool = True
    trail_distance_pct: float = Field(default=10.0, ge=2.0, le=30.0)


@router.post("/api/paper/management/config", dependencies=[Depends(require_admin_token)])
def update_paper_management(body: PaperManagementConfigRequest):
    trade = store.get_open_paper_trade()
    if not trade:
        raise HTTPException(status_code=404, detail="No open paper trade")
    from app.paper_trade_management import ensure_management, configure
    ensure_management(trade)
    return configure(trade["id"], trailing_enabled=body.trailing_enabled,
                     trail_distance_pct=body.trail_distance_pct)


@router.get("/api/paper/monitor/status")
def paper_monitor_status():
    from app.paper_monitor import status_snapshot
    return status_snapshot()


@router.get("/api/paper/monitor/events")
def paper_monitor_events(trade_id: int | None = None, limit: int = 100):
    return {"events": store.list_paper_monitor_events(trade_id=trade_id, limit=limit)}


@router.post("/api/paper/monitor/run-once", dependencies=[Depends(require_admin_token)])
def paper_monitor_run_once():
    from app.paper_monitor import monitor_once
    return monitor_once(get_data_source())


@router.get("/api/risk/status")
def get_risk_status():
    return risk_status()


class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: str | None = Field(default=None, max_length=500)


@router.post("/api/risk/kill-switch", dependencies=[Depends(require_admin_token)])
def update_kill_switch(body: KillSwitchRequest):
    if body.enabled and not body.reason:
        raise HTTPException(status_code=422, detail="A reason is required when enabling the kill switch")
    return store.set_kill_switch(body.enabled, body.reason)


@router.get("/api/analytics/paper")
def get_paper_analytics():
    return store.paper_analytics_summary()


@router.get("/api/replay")
def list_replays(limit: int = 50):
    return {"replays": store.list_decision_replays(limit)}


@router.get("/api/replay/{trade_id}")
def get_replay(trade_id: int):
    replay = store.get_decision_replay(trade_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="Paper trade not found")
    return replay


@router.get("/api/operations/system")
def operations_system():
    from app.operations import system_snapshot
    return system_snapshot()


@router.get("/api/operations/logs")
def operations_logs(limit: int = 100):
    from app.operations import recent_logs
    return recent_logs(limit)


@router.get("/api/operations/deployments")
def operations_deployments():
    from app.operations import deployment_snapshot
    return deployment_snapshot()


@router.get("/api/agents/registry")
def agents_registry():
    from app.agent_registry import registry_snapshot
    ds = get_data_source()
    response = run_observed_pipeline(run_pipeline, ds, position=_current_position_info())
    return registry_snapshot(response)


@router.get("/api/strategy-lab/sample")
def strategy_lab_sample():
    from app.strategy_lab import sample_payload
    return sample_payload()


class StrategyLabRequest(BaseModel):
    name: str = Field(default="Unnamed Strategy", max_length=120)
    candles: list[dict]
    signals: list[dict]
    config: dict = Field(default_factory=dict)
    walk_forward: dict = Field(default_factory=dict)


@router.post("/api/strategy-lab/validate")
def strategy_lab_validate(body: StrategyLabRequest):
    from app.strategy_lab import validate_strategy
    try:
        return validate_strategy(body.model_dump())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc




@router.get("/api/live-data/status")
def live_data_status():
    from app.market_data_service import get_supervisor
    return get_supervisor(
        settings.market_data_state_path,
        settings.market_data_poll_interval_sec,
        settings.max_data_age_sec,
        settings.kite_websocket_requested,
    ).snapshot()


@router.post("/api/live-data/poll", dependencies=[Depends(require_admin_token)])
def live_data_poll():
    from app.market_data_service import get_supervisor
    return get_supervisor(
        settings.market_data_state_path,
        settings.market_data_poll_interval_sec,
        settings.max_data_age_sec,
        settings.kite_websocket_requested,
    ).poll_once(get_data_source())


@router.post("/api/live-data/instruments/sync", dependencies=[Depends(require_admin_token)])
def live_data_instrument_sync():
    from app.market_data_service import get_supervisor
    try:
        return get_supervisor(
            settings.market_data_state_path,
            settings.market_data_poll_interval_sec,
            settings.max_data_age_sec,
            settings.kite_websocket_requested,
        ).sync_instruments(get_data_source())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/live-data/candles")
def live_data_candles():
    from app.market_data_service import get_supervisor
    state = get_supervisor(
        settings.market_data_state_path,
        settings.market_data_poll_interval_sec,
        settings.max_data_age_sec,
        settings.kite_websocket_requested,
    ).snapshot()
    return {"timeframe": "3m", "candles": state.get("candles_3m", []), "fresh": state.get("fresh", False)}


@router.post("/api/live-data/refresh", dependencies=[Depends(require_admin_token)])
def live_data_refresh():
    from app.market_data_service import get_supervisor
    return get_supervisor(
        settings.market_data_state_path,
        settings.market_data_poll_interval_sec,
        settings.max_data_age_sec,
        settings.kite_websocket_requested,
    ).poll_once(get_data_source())


class OrderPreviewRequest(BaseModel):
    tradingsymbol: str = Field(min_length=3, max_length=80)
    transaction_type: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    product: Literal["MIS", "NRML"] = "MIS"
    estimated_price: float = Field(gt=0)
    price: float | None = Field(default=None, gt=0)
    idempotency_key: str | None = Field(default=None, max_length=100)


@router.post("/api/execution/preview", dependencies=[Depends(require_admin_token)])
def execution_preview(body: OrderPreviewRequest):
    from app.execution_readiness import create_preview
    return create_preview(body.model_dump(), settings.paper_capital, settings.max_capital_utilization_pct, settings.nifty_lot_size)


class OrderConfirmRequest(BaseModel):
    preview_id: str = Field(min_length=5, max_length=100)
    confirmation_text: str = Field(min_length=1, max_length=20)


@router.post("/api/execution/confirm", dependencies=[Depends(require_admin_token)])
def execution_confirm(body: OrderConfirmRequest):
    from app.execution_readiness import confirm
    try:
        return confirm(body.preview_id, body.confirmation_text, settings.live_orders_enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/api/execution/orders")
def execution_orders():
    from app.execution_readiness import list_orders
    return {"orders": list_orders(), "live_orders_enabled": settings.live_orders_enabled}


@router.get("/api/security/status")
def get_security_status():
    from app.security import security_status
    return security_status()


@router.get("/api/analytics/backtest")
def get_backtest_summary():
    """Evaluates logged GENERATED decisions against forward price data.
    In mock mode there's no real forward price history to replay against
    (the mock generator doesn't persist a timeline), so this reports the
    audit log size and points to app/backtest.py for wiring up real
    historical data once TRADING_MODE=live and Zerodha history is available.
    See app/backtest.py::evaluate_audit_log for the real entrypoint."""
    from app.backtest import load_audit_log
    records = load_audit_log(settings.audit_log_path)
    generated = [r for r in records if r.get("outcome_status") == "GENERATED"]
    return {
        "audit_log_entries": len(records),
        "generated_decisions": len(generated),
        "note": (
            "Backtest evaluation requires forward price data per trade "
            "(see app/backtest.py::evaluate_audit_log). Wire a price_lookup "
            "callable against your Zerodha historical data once live; this "
            "endpoint currently only reports what's been logged."
        ),
    }


def _build_and_log_live_decision():
    """Shared by the REST endpoint and the WebSocket loop so both paths log
    identically and never drift out of sync."""
    global _last_logged_signature
    ds = get_data_source()
    resp = run_observed_pipeline(run_pipeline, ds, position=_current_position_info())

    signature = _decision_signature(resp)
    if signature != _last_logged_signature:
        if not resp.risk.approved:
            outcome = "BLOCKED"
        elif resp.decision.decision.value == "NO_TRADE":
            outcome = "SKIPPED"
        else:
            outcome = "GENERATED"
        log_decision(resp, outcome_status=outcome)
        if outcome == "GENERATED":
            payload = from_dataclass(resp).model_dump(mode="json")
            setup_signature = hashlib.sha256(
                json.dumps({
                    "trading_day": resp.timestamp[:10],
                    "decision": payload["decision"]["decision"],
                    "grade": payload["decision"]["grade"],
                    "strike": (payload["decision"].get("plan") or {}).get("strike"),
                    "entry_low": (payload["decision"].get("plan") or {}).get("entry_low"),
                    "entry_high": (payload["decision"].get("plan") or {}).get("entry_high"),
                }, sort_keys=True).encode("utf-8")
            ).hexdigest()
            store.create_trade_setup(setup_signature, payload)
        _last_logged_signature = signature
    return resp


@router.websocket("/ws/decision")
async def ws_decision(websocket: WebSocket):
    """Real-time push replacement for polling (spec section 32). The
    frontend's useLiveDecision hook will use this automatically when
    available and fall back to polling /api/decision/live if the socket
    can't connect — see frontend/src/hooks/useLiveDecision.ts.

    Sends the same JSON shape as GET /api/decision/live so no client-side
    parsing changes are needed when switching between the two."""
    await websocket.accept()
    last_sent_signature = None
    try:
        while True:
            resp = await asyncio.to_thread(_build_and_log_live_decision)
            signature = _decision_signature(resp)
            schema = from_dataclass(resp)
            await websocket.send_text(schema.model_dump_json())
            last_sent_signature = signature
            await asyncio.sleep(settings.poll_interval_sec)
    except WebSocketDisconnect:
        pass
